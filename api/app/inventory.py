"""Lager fra brain (§2.3) + stabilt hash til recompute-gating (§4.1).

Madplan taler ALDRIG direkte med Vikunja (§A4) — kun med brains
/api/internal/inventory. Tomt INTERNAL_API_TOKEN ⇒ tomt lager (feed slået fra).
"""
import hashlib
import json

import httpx

from . import config


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
