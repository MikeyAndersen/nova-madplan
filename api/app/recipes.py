"""Opskrifts-katalog: scrape-preview, CRUD, cachet billede. Sletning nulstiller
dishes.recipe_id (semantik: ON DELETE SET NULL, håndteret i app-laget)."""
import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from . import config, db, scrape
from .auth import require_api_token
from .models import Recipe, RecipeCreate, RecipePatch, ScrapePreview

router = APIRouter(prefix="/api/recipes", dependencies=[Depends(require_api_token)])


def _now_iso() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(timespec="seconds")


class ScrapeBody(BaseModel):
    url: str


class RecipeCreateBody(RecipeCreate):
    image_url: str | None = None


def row_to_recipe(row: sqlite3.Row) -> Recipe:
    return Recipe(id=row["id"], title=row["title"], source_url=row["source_url"],
                  ingredients=json.loads(row["ingredients"]),
                  steps=json.loads(row["steps"]), time_min=row["time_min"],
                  tags=json.loads(row["tags"]), raw_snapshot=row["raw_snapshot"],
                  has_image=row["image_mime"] is not None,
                  created_at=row["created_at"], updated_at=row["updated_at"])


@router.post("/scrape", response_model=ScrapePreview)
def scrape_url(body: ScrapeBody) -> ScrapePreview:
    try:
        return scrape.scrape_recipe_smart(body.url)
    except Exception:
        raise HTTPException(status_code=502,
                            detail="Kunne ikke hente siden. Prøv igen eller indtast manuelt.")


@router.get("", response_model=list[Recipe])
def list_recipes(q: str | None = Query(default=None)) -> list[Recipe]:
    sql = ("SELECT id, title, source_url, ingredients, steps, time_min, tags,"
           " raw_snapshot, image_mime, created_at, updated_at FROM recipes")
    params: list = []
    if q:
        sql += " WHERE title LIKE ? OR ingredients LIKE ?"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY updated_at DESC"
    with db.connect() as conn:
        return [row_to_recipe(r) for r in conn.execute(sql, params)]


@router.post("", response_model=Recipe, status_code=201)
def create_recipe(body: RecipeCreateBody) -> Recipe:
    now = _now_iso()
    image = scrape.fetch_image(body.image_url) if body.image_url else None
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO recipes(title, source_url, ingredients, steps, time_min,"
            " tags, raw_snapshot, image_mime, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (body.title.strip(), body.source_url,
             json.dumps([i.model_dump() for i in body.ingredients], ensure_ascii=False),
             json.dumps(body.steps, ensure_ascii=False), body.time_min,
             json.dumps(body.tags, ensure_ascii=False), body.raw_snapshot,
             image[1] if image else None, now, now))
        rid = cur.lastrowid
        if image:
            conn.execute("INSERT INTO recipe_images(recipe_id, bytes, mime) VALUES(?,?,?)",
                         (rid, image[0], image[1]))
        row = conn.execute("SELECT * FROM recipes WHERE id = ?", (rid,)).fetchone()
    return row_to_recipe(row)


@router.get("/{recipe_id}", response_model=Recipe)
def get_recipe(recipe_id: int) -> Recipe:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
    return row_to_recipe(row)


@router.patch("/{recipe_id}", response_model=Recipe)
def patch_recipe(recipe_id: int, body: RecipePatch) -> Recipe:
    fields = body.model_dump(exclude_unset=True)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
        sets, params = [], []
        for key, value in fields.items():
            if key == "ingredients":
                value = json.dumps([i if isinstance(i, dict) else i.model_dump()
                                    for i in value], ensure_ascii=False)
            elif key in ("steps", "tags"):
                value = json.dumps(value, ensure_ascii=False)
            elif key == "title" and value:
                value = value.strip()
            sets.append(f"{key} = ?")
            params.append(value)
        if sets:
            sets.append("updated_at = ?")
            params.append(_now_iso())
            conn.execute(f"UPDATE recipes SET {', '.join(sets)} WHERE id = ?",
                         (*params, recipe_id))
        row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return row_to_recipe(row)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int) -> Response:
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
        conn.execute("DELETE FROM recipe_images WHERE recipe_id = ?", (recipe_id,))
        conn.execute("UPDATE dishes SET recipe_id = NULL WHERE recipe_id = ?", (recipe_id,))
    return Response(status_code=204)


@router.get("/{recipe_id}/image")
def get_recipe_image(recipe_id: int) -> Response:
    with db.connect() as conn:
        row = conn.execute("SELECT bytes, mime FROM recipe_images WHERE recipe_id = ?",
                           (recipe_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No image")
    return Response(content=row["bytes"], media_type=row["mime"])
