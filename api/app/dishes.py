"""Dish-CRUD (spec §3.1). DELETE er soft delete: active=false, historik bevares."""
import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import config, db
from .auth import require_api_token
from .models import Dish, DishCreate, DishUpdate

router = APIRouter(prefix="/api/dishes", dependencies=[Depends(require_api_token)])


def _now_iso() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(timespec="seconds")


def row_to_dish(row: sqlite3.Row) -> Dish:
    return Dish(id=row["id"], name=row["name"], tags=json.loads(row["tags"]),
                recurring_weekly=bool(row["recurring_weekly"]),
                ingredients=json.loads(row["ingredients"]),
                last_made=row["last_made"], active=bool(row["active"]))


@router.get("", response_model=list[Dish])
def list_dishes(include_inactive: bool = Query(default=True)) -> list[Dish]:
    sql = "SELECT * FROM dishes"
    if not include_inactive:
        sql += " WHERE active = 1"
    with db.connect() as conn:
        return [row_to_dish(r) for r in conn.execute(sql + " ORDER BY name COLLATE NOCASE")]


@router.get("/{dish_id}", response_model=Dish)
def get_dish(dish_id: int) -> Dish:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Dish {dish_id} not found")
    return row_to_dish(row)


@router.post("", response_model=Dish, status_code=201)
def create_dish(body: DishCreate) -> Dish:
    now = _now_iso()
    with db.connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO dishes(name, tags, recurring_weekly, ingredients, active,"
                " created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                (body.name.strip(), json.dumps(body.tags, ensure_ascii=False),
                 int(body.recurring_weekly),
                 json.dumps([i.model_dump() for i in body.ingredients], ensure_ascii=False),
                 int(body.active), now, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail=f"Dish name {body.name!r} already exists")
        row = conn.execute("SELECT * FROM dishes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_to_dish(row)


@router.put("/{dish_id}", response_model=Dish)
def update_dish(dish_id: int, body: DishUpdate) -> Dish:
    fields = body.model_dump(exclude_unset=True)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Dish {dish_id} not found")
        sets, params = [], []
        for key, value in fields.items():
            if key in ("tags", "ingredients"):
                value = json.dumps(value, ensure_ascii=False)
            elif key == "name":
                value = value.strip()
            elif key in ("recurring_weekly", "active"):
                value = int(value)
            sets.append(f"{key} = ?")
            params.append(value)
        if sets:
            sets.append("updated_at = ?")
            params.append(_now_iso())
            try:
                conn.execute(f"UPDATE dishes SET {', '.join(sets)} WHERE id = ?", (*params, dish_id))
            except sqlite3.IntegrityError:
                raise HTTPException(status_code=409, detail="Dish name already exists")
        row = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    return row_to_dish(row)


@router.delete("/{dish_id}", status_code=204)
def delete_dish(dish_id: int) -> Response:
    with db.connect() as conn:
        cur = conn.execute("UPDATE dishes SET active = 0, updated_at = ? WHERE id = ?",
                           (_now_iso(), dish_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Dish {dish_id} not found")
    return Response(status_code=204)
