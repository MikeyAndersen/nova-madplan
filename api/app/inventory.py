"""Lager fra brain (§2.3) + stabilt hash til recompute-gating (§4.1).

Madplan taler ALDRIG direkte med Vikunja (§A4) — kun med brains
/api/internal/inventory. Tomt INTERNAL_API_TOKEN ⇒ tomt lager (feed slået fra).
"""
import hashlib
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import config, db
from .auth import require_api_token
from .models import InventoryBulkIn, InventoryItem, InventoryPatch

router = APIRouter(prefix="/api/inventory", dependencies=[Depends(require_api_token)])


def _now_iso() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(timespec="seconds")


def name_key(name: str) -> str:
    """Normaliseret navn til merge-på-navn (§8): lowercase, kollapset whitespace."""
    return re.sub(r"\s+", " ", name.strip().lower())


@router.get("", response_model=list[InventoryItem])
def list_inventory(q: str | None = Query(default=None),
                   category: str | None = Query(default=None)) -> list[InventoryItem]:
    sql, params, where = "SELECT * FROM inventory_items", [], []
    if q:
        where.append("name LIKE ?")
        params.append(f"%{q}%")
    if category:
        where.append("category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, name COLLATE NOCASE"
    with db.connect() as conn:
        return [InventoryItem(**dict(r)) for r in conn.execute(sql, params)]


@router.post("", status_code=201)
def bulk_add(body: InventoryBulkIn) -> dict:
    """Bulk create (nemlig-import + manuel). merge=True lægger quantity til
    eksisterende række med samme name_key i stedet for at duplikere."""
    now = _now_iso()
    added = merged = 0
    with db.connect() as conn:
        for item in body.items:
            key = name_key(item.name)
            if not key:
                continue
            existing = conn.execute("SELECT id FROM inventory_items WHERE name_key = ?",
                                    (key,)).fetchone() if body.merge else None
            if existing:
                conn.execute(
                    "UPDATE inventory_items SET quantity = quantity + ?, updated_at = ?"
                    " WHERE id = ?", (item.quantity, now, existing["id"]))
                merged += 1
            else:
                conn.execute(
                    "INSERT INTO inventory_items(name, name_key, quantity, unit, note,"
                    " category, source, added_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (item.name.strip(), key, item.quantity, item.unit, item.note,
                     item.category, item.source, now, now))
                added += 1
    return {"added": added, "merged": merged}


@router.patch("/{item_id}", response_model=InventoryItem)
def patch_item(item_id: int, body: InventoryPatch) -> InventoryItem:
    fields = body.model_dump(exclude_unset=True)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        sets, params = [], []
        for key, value in fields.items():
            if key == "name":
                value = value.strip()
                sets.append("name_key = ?")
                params.append(name_key(value))
            sets.append(f"{key} = ?")
            params.append(value)
        if sets:
            sets.append("updated_at = ?")
            params.append(_now_iso())
            conn.execute(f"UPDATE inventory_items SET {', '.join(sets)} WHERE id = ?",
                         (*params, item_id))
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
    return InventoryItem(**dict(row))


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int) -> Response:
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return Response(status_code=204)


async def fetch() -> list[dict]:
    if not config.INTERNAL_API_TOKEN:
        return []
    url = f"{config.BRAIN_URL.rstrip('/')}/api/internal/inventory"
    headers = {"Authorization": f"Bearer {config.INTERNAL_API_TOKEN}"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json() or []


def hash_inventory(items: list[dict]) -> str:
    """sha256 over de felter der påvirker forslag (navn+bucket+done pr. task).
    Uændret hash ⇒ ingen grund til at genberegne (§4.1)."""
    canon = sorted(
        [str(i.get("vikunja_task_id")), (i.get("name") or ""),
         (i.get("bucket") or ""), str(bool(i.get("done")))]
        for i in items
    )
    digest = hashlib.sha256(json.dumps(canon, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"
