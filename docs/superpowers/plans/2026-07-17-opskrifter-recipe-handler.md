# Opskrifter (recipe handler) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A recipe cookbook (`/opskrifter`) where recipes are scraped from a URL and cached (structured fields + raw snapshot + image bytes) so they survive sites changing or going down.

**Architecture:** New backend entity `recipes` in the existing FastAPI+SQLite service, with scraping in Python (network isolated from pure parsing for testability). Dishes gain an optional `recipe_id`. Frontend adds an Astro cookbook page + detail page + BFF proxy routes; images are streamed through the BFF so the backend token never reaches the browser.

**Tech Stack:** FastAPI, SQLite (sqlite3), Pydantic v2, `recipe-scrapers` (structured parse), `trafilatura` (raw snapshot), httpx (already a dep); Astro SSR on Cloudflare Workers; pytest (backend), vitest (frontend).

## Global Constraints

- **Language:** documentation/UI Danish; code/API/JSON English. Copy verbatim from spec.
- **Auth:** every `/api/*` route is Bearer-gated via `Depends(require_api_token)`. The token (`LIFEHUB_API_TOKEN`) MUST NEVER reach the client bundle — frontend always goes through the BFF (`getApi()` in `src/lib/api.ts`).
- **DB:** one SQLite file (`config.DATABASE_PATH`), `CREATE TABLE IF NOT EXISTS` in `db._SCHEMA`; new columns on existing tables via explicit `ALTER TABLE` in `init_db()`. `PRAGMA foreign_keys=ON` is already set per connection.
- **Timestamps:** ISO seconds in `config.TIMEZONE` via the module-local `_now_iso()` helper (copy the existing one).
- **Tests mock the network boundary** with `monkeypatch.setattr` (see `api/tests/test_drain.py`); never make real HTTP calls in tests.
- **Commits:** conventional-commit style, one per task step as shown. Do NOT push (user pushes explicitly).
- **Backend deploy is manual on LXC 103** (new Python deps → `docker compose up -d --build`); the implementer cannot deploy. Frontend deploy is `npx wrangler deploy`.

---

## File Structure

**Backend (`api/`):**
- `app/db.py` — MODIFY: add `recipes` + `recipe_images` tables to `_SCHEMA`; add `dishes.recipe_id` migration in `init_db()`.
- `app/models.py` — MODIFY: add `Recipe`, `RecipeInput`, `RecipeCreate`, `RecipePatch`, `ScrapePreview`; add `recipe_id` to `Dish`/`DishUpdate`.
- `app/scrape.py` — CREATE: network fetch fns + pure parse fns.
- `app/recipes.py` — CREATE: `/api/recipes` router (CRUD + scrape + image).
- `app/dishes.py` — MODIFY: read/write `recipe_id`.
- `app/main.py` — MODIFY: register recipes router.
- `requirements.txt` — MODIFY: add `recipe-scrapers`, `trafilatura`.
- `tests/test_scrape.py`, `tests/test_recipes.py`, `tests/fixtures/` — CREATE.

**Frontend (repo root):**
- `src/lib/api.types.ts` — MODIFY: add `Recipe`, `RecipeInput`, `ScrapePreview`; `recipe_id` on `Dish`.
- `src/lib/api.ts` — MODIFY: add recipe methods.
- `src/pages/api/recipes/*.ts` — CREATE: BFF routes (scrape, crud, image).
- `src/pages/opskrifter/index.astro` — CREATE: cookbook list + add.
- `src/pages/opskrifter/[id].astro` — CREATE: detail + edit + dish link.
- `src/components/RecipeForm.astro` — CREATE: shared add/edit form.
- `src/components/Nav.astro` — MODIFY: add "Opskrifter".
- `src/components/MealCard.astro` — MODIFY: show recipe link when dish has one.
- `tests/recipes/*.test.ts` — CREATE.

---

## Task 1: DB schema — recipes, recipe_images, dishes.recipe_id

**Files:**
- Modify: `api/app/db.py`
- Test: `api/tests/test_recipes_db.py`

**Interfaces:**
- Produces: tables `recipes(id, title, source_url, ingredients, steps, time_min, tags, raw_snapshot, image_mime, created_at, updated_at)`, `recipe_images(recipe_id PK, bytes, mime)`, and column `dishes.recipe_id INTEGER`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_recipes_db.py
from app import db


def test_schema_has_recipe_tables_and_dish_column(client):
    with db.connect() as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "recipes" in tables
        assert "recipe_images" in tables
        dish_cols = {r["name"] for r in conn.execute("PRAGMA table_info(dishes)")}
        assert "recipe_id" in dish_cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_recipes_db.py -v`
Expected: FAIL (`recipes` not in tables).

- [ ] **Step 3: Add tables to `_SCHEMA` and the column migration**

In `api/app/db.py`, append inside the `_SCHEMA` string (before the closing `"""`, after the `inventory_items` block):

```sql

-- Opskrifter: scrapet + cachet. ingredients/steps/tags = JSON. raw_snapshot =
-- fuld readable sidetekst (sikkerhedsnet). image_mime sat ⇒ billede findes.
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_url TEXT,
    ingredients TEXT NOT NULL DEFAULT '[]',
    steps TEXT NOT NULL DEFAULT '[]',
    time_min INTEGER,
    tags TEXT NOT NULL DEFAULT '[]',
    raw_snapshot TEXT NOT NULL DEFAULT '',
    image_mime TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Billed-bytes adskilt så list-queries ikke trækker BLOBs. Cascade-slet med opskrift.
CREATE TABLE IF NOT EXISTS recipe_images (
    recipe_id INTEGER PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
    bytes BLOB NOT NULL,
    mime TEXT NOT NULL
);
```

Then change `init_db()` to add the `dishes.recipe_id` column when missing:

```python
def init_db() -> None:
    os.makedirs(os.path.dirname(config.DATABASE_PATH) or ".", exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(dishes)")}
        if "recipe_id" not in cols:
            conn.execute("ALTER TABLE dishes ADD COLUMN recipe_id INTEGER")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_recipes_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/db.py api/tests/test_recipes_db.py
git commit -m "feat(recipes): recipes + recipe_images tabeller + dishes.recipe_id"
```

---

## Task 2: Pydantic models

**Files:**
- Modify: `api/app/models.py`
- Test: `api/tests/test_recipe_models.py`

**Interfaces:**
- Produces: `Recipe`, `RecipeInput`, `RecipeCreate`, `RecipePatch`, `ScrapePreview`; `Dish.recipe_id`, `DishUpdate.recipe_id`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_recipe_models.py
from app.models import Recipe, RecipeCreate, ScrapePreview


def test_recipe_create_defaults():
    rc = RecipeCreate(title="Kødsovs")
    assert rc.ingredients == [] and rc.steps == [] and rc.source_url is None


def test_scrape_preview_shape():
    sp = ScrapePreview(parsed=RecipeCreate(title="X"), image_url=None, ok=True)
    assert sp.ok is True and sp.parsed.title == "X"


def test_recipe_has_image_flag():
    r = Recipe(id=1, title="X", ingredients=[], steps=[], tags=[],
              raw_snapshot="", has_image=True, source_url=None, time_min=None,
              created_at="t", updated_at="t")
    assert r.has_image is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_recipe_models.py -v`
Expected: FAIL (ImportError: cannot import name 'Recipe').

- [ ] **Step 3: Add the models**

Append to `api/app/models.py` (reuses the existing `Ingredient` model):

```python
# ── Opskrifter ──────────────────────────────────────────────────────
class RecipeCreate(BaseModel):
    title: str = Field(min_length=1)
    source_url: str | None = None
    ingredients: list[Ingredient] = []
    steps: list[str] = []
    time_min: int | None = None
    tags: list[str] = []
    raw_snapshot: str = ""


class RecipeInput(RecipeCreate):
    """Alias for readability at call sites; identical shape to RecipeCreate."""


class RecipePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    source_url: str | None = None
    ingredients: list[Ingredient] | None = None
    steps: list[str] | None = None
    time_min: int | None = None
    tags: list[str] | None = None
    raw_snapshot: str | None = None


class Recipe(RecipeCreate):
    id: int
    has_image: bool = False
    created_at: str
    updated_at: str


class ScrapePreview(BaseModel):
    parsed: RecipeCreate
    image_url: str | None = None
    ok: bool = True
    warning: str | None = None
```

Add `recipe_id` to the existing `Dish` and `DishUpdate` models (add one line to each):

```python
# in class Dish(BaseModel): add after `active`
    recipe_id: int | None = None

# in class DishUpdate(BaseModel): add after `active`
    recipe_id: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_recipe_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_recipe_models.py
git commit -m "feat(recipes): pydantic-modeller + Dish.recipe_id"
```

---

## Task 3: Scrape module (network isolated from parsing)

**Files:**
- Create: `api/app/scrape.py`
- Modify: `api/requirements.txt`
- Create: `api/tests/fixtures/recipe_jsonld.html`, `api/tests/fixtures/plain.html`
- Test: `api/tests/test_scrape.py`

**Interfaces:**
- Produces:
  - `fetch_html(url: str) -> str` (network; monkeypatched in tests)
  - `fetch_image(url: str) -> tuple[bytes, str] | None` (network; returns bytes+mime or None)
  - `parse_recipe(html: str, url: str) -> ScrapePreview` (pure)
  - `extract_snapshot(html: str) -> str` (pure)

- [ ] **Step 1: Add dependencies**

Append to `api/requirements.txt`:

```
recipe-scrapers>=15
trafilatura>=1.8
```

Install locally into the venv used for tests:
Run: `cd api && python -m pip install "recipe-scrapers>=15" "trafilatura>=1.8"`

- [ ] **Step 2: Write the fixtures**

`api/tests/fixtures/recipe_jsonld.html` — a minimal page carrying schema.org Recipe JSON-LD:

```html
<!doctype html><html><head><title>Kødsovs</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Recipe","name":"Kødsovs",
 "recipeIngredient":["500 g hakket oksekød","1 løg","2 dåser flåede tomater"],
 "recipeInstructions":[{"@type":"HowToStep","text":"Brun kød og løg."},
   {"@type":"HowToStep","text":"Tilsæt tomater og simr 30 min."}],
 "totalTime":"PT45M","image":"https://example.com/kodsovs.jpg"}
</script></head>
<body><h1>Kødsovs</h1><p>En klassiker.</p></body></html>
```

`api/tests/fixtures/plain.html` — a page with NO structured recipe data:

```html
<!doctype html><html><head><title>Note</title></head>
<body><article><h1>Mormors frikadeller</h1>
<p>Bland fars, form boller, steg gyldne. Serveres med kartofler.</p>
</article></body></html>
```

- [ ] **Step 3: Write the failing test**

```python
# api/tests/test_scrape.py
import pathlib

from app import scrape

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_parse_structured_recipe():
    sp = scrape.parse_recipe(_read("recipe_jsonld.html"), "https://example.com/r")
    assert sp.ok is True
    assert sp.parsed.title == "Kødsovs"
    assert len(sp.parsed.ingredients) == 3
    assert sp.parsed.ingredients[0].name == "500 g hakket oksekød"
    assert len(sp.parsed.steps) == 2
    assert sp.parsed.time_min == 45
    assert sp.image_url == "https://example.com/kodsovs.jpg"
    assert sp.parsed.raw_snapshot  # snapshot always present


def test_parse_plain_page_fails_soft():
    sp = scrape.parse_recipe(_read("plain.html"), "https://example.com/note")
    assert sp.ok is False
    assert sp.warning  # tells the user to fill fields in
    assert sp.parsed.raw_snapshot  # snapshot still captured
    assert sp.parsed.title  # falls back to <title> or url, never empty


def test_extract_snapshot_returns_text():
    text = scrape.extract_snapshot(_read("plain.html"))
    assert "frikadeller" in text.lower()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_scrape.py -v`
Expected: FAIL (ModuleNotFoundError: app.scrape).

- [ ] **Step 5: Implement `api/app/scrape.py`**

```python
"""Recipe-scraping: netværks-fetch adskilt fra ren parsing (så tests er
netværksfri). parse_recipe fejler blødt — returnerer altid et snapshot og
en ikke-tom titel, selv når der ikke er strukturerede data."""
from urllib.parse import urlparse

import httpx
import trafilatura
from recipe_scrapers import scrape_html

from .models import Ingredient, RecipeCreate, ScrapePreview

_UA = "Mozilla/5.0 (compatible; nova-madplan/1.0; +https://madplan.nova-tech.dk)"
_TIMEOUT = httpx.Timeout(15.0)


def fetch_html(url: str) -> str:
    r = httpx.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT,
                  follow_redirects=True)
    r.raise_for_status()
    return r.text


def fetch_image(url: str) -> tuple[bytes, str] | None:
    try:
        r = httpx.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT,
                      follow_redirects=True)
        r.raise_for_status()
    except Exception:
        return None
    mime = r.headers.get("content-type", "").split(";")[0].strip()
    if not mime.startswith("image/") or not r.content:
        return None
    return r.content, mime


def extract_snapshot(html: str) -> str:
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    return text or ""


def _title_from_html(html: str, url: str) -> str:
    import re
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return urlparse(url).netloc or "Ny opskrift"


def parse_recipe(html: str, url: str) -> ScrapePreview:
    snapshot = extract_snapshot(html)
    try:
        s = scrape_html(html, org_url=url, wild_mode=True)
        title = (s.title() or "").strip()
        ingredients = [Ingredient(name=i.strip()) for i in (s.ingredients() or []) if i.strip()]
        steps = [x.strip() for x in (s.instructions_list() or []) if x.strip()]
        try:
            total = s.total_time()
            time_min = int(total) if total else None
        except Exception:
            time_min = None
        try:
            image_url = s.image() or None
        except Exception:
            image_url = None
        if title and (ingredients or steps):
            return ScrapePreview(
                parsed=RecipeCreate(title=title, source_url=url, ingredients=ingredients,
                                    steps=steps, time_min=time_min, raw_snapshot=snapshot),
                image_url=image_url, ok=True)
    except Exception:
        pass
    # fail-soft: intet struktureret — behold snapshot + gæt titel
    return ScrapePreview(
        parsed=RecipeCreate(title=_title_from_html(html, url), source_url=url,
                            raw_snapshot=snapshot),
        image_url=None, ok=False,
        warning="Kunne ikke læse strukturerede data — udfyld felterne selv (teksten er gemt).")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_scrape.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add api/app/scrape.py api/requirements.txt api/tests/test_scrape.py api/tests/fixtures/
git commit -m "feat(recipes): scrape-modul (struktureret parse + rå snapshot, fail-soft)"
```

---

## Task 4: Recipes router (CRUD + scrape + image)

**Files:**
- Create: `api/app/recipes.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_recipes.py`

**Interfaces:**
- Consumes: `scrape.fetch_html`, `scrape.parse_recipe`, `scrape.fetch_image`; models from Task 2.
- Produces: router at `/api/recipes` with `POST /scrape`, `GET ""`, `POST ""`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `GET /{id}/image`. On `DELETE`, nulls `dishes.recipe_id` referencing it.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_recipes.py
from app import recipes, scrape

HTML = """<!doctype html><html><head><title>T</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Recipe",
"name":"Kødsovs","recipeIngredient":["500 g kød"],
"recipeInstructions":[{"@type":"HowToStep","text":"Brun."}],"totalTime":"PT20M",
"image":"https://x/i.jpg"}</script></head><body></body></html>"""


def test_scrape_preview_then_create(client, monkeypatch):
    monkeypatch.setattr(scrape, "fetch_html", lambda url: HTML)
    r = client.post("/api/recipes/scrape", json={"url": "https://x/r"},
                    headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    prev = r.json()
    assert prev["ok"] is True and prev["parsed"]["title"] == "Kødsovs"

    monkeypatch.setattr(scrape, "fetch_image", lambda url: (b"\xff\xd8\xff", "image/jpeg"))
    body = {**prev["parsed"], "image_url": prev["image_url"]}
    c = client.post("/api/recipes", json=body,
                    headers={"Authorization": "Bearer test-token"})
    assert c.status_code == 201
    rid = c.json()["id"]
    assert c.json()["has_image"] is True

    img = client.get(f"/api/recipes/{rid}/image",
                     headers={"Authorization": "Bearer test-token"})
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


def test_create_manual_without_url(client):
    c = client.post("/api/recipes", json={"title": "Mormors frikadeller",
                    "ingredients": [{"name": "fars"}], "steps": ["Steg."]},
                    headers={"Authorization": "Bearer test-token"})
    assert c.status_code == 201 and c.json()["has_image"] is False


def test_list_search_and_delete_nulls_dish_link(client):
    rid = client.post("/api/recipes", json={"title": "Tacos"},
                      headers={"Authorization": "Bearer test-token"}).json()["id"]
    did = client.post("/api/dishes", json={"name": "Tacos"},
                      headers={"Authorization": "Bearer test-token"}).json()["id"]
    client.put(f"/api/dishes/{did}", json={"recipe_id": rid},
               headers={"Authorization": "Bearer test-token"})
    assert client.get("/api/recipes?q=taco",
                      headers={"Authorization": "Bearer test-token"}).json()[0]["id"] == rid
    assert client.delete(f"/api/recipes/{rid}",
                         headers={"Authorization": "Bearer test-token"}).status_code == 204
    dish = client.get(f"/api/dishes/{did}",
                      headers={"Authorization": "Bearer test-token"}).json()
    assert dish["recipe_id"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_recipes.py -v`
Expected: FAIL (ModuleNotFoundError: app.recipes).

- [ ] **Step 3: Implement `api/app/recipes.py`**

```python
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
        html = scrape.fetch_html(body.url)
    except Exception:
        raise HTTPException(status_code=502,
                            detail="Kunne ikke hente siden. Prøv igen eller indtast manuelt.")
    return scrape.parse_recipe(html, body.url)


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
```

- [ ] **Step 4: Register the router in `api/app/main.py`**

Add `recipes` to the import and include its router:

```python
from . import config, db, dishes, inventory, recipes, suggest, suggestions, weekplan
# ...
app.include_router(recipes.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_recipes.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add api/app/recipes.py api/app/main.py api/tests/test_recipes.py
git commit -m "feat(recipes): /api/recipes router (scrape, CRUD, cachet billede)"
```

---

## Task 5: Dish ↔ recipe link in dishes.py

**Files:**
- Modify: `api/app/dishes.py`
- Test: `api/tests/test_dish_recipe_link.py`

**Interfaces:**
- Consumes: `dishes.recipe_id` column (Task 1), `Dish.recipe_id` (Task 2).
- Produces: `row_to_dish` returns `recipe_id`; `create_dish`/`update_dish` accept it.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_dish_recipe_link.py
def test_dish_carries_recipe_id(client):
    rid = client.post("/api/recipes", json={"title": "Chili"},
                      headers={"Authorization": "Bearer test-token"}).json()["id"]
    did = client.post("/api/dishes", json={"name": "Chili con carne", "recipe_id": rid},
                      headers={"Authorization": "Bearer test-token"}).json()["id"]
    assert client.get(f"/api/dishes/{did}",
                      headers={"Authorization": "Bearer test-token"}).json()["recipe_id"] == rid
    client.put(f"/api/dishes/{did}", json={"recipe_id": None},
               headers={"Authorization": "Bearer test-token"})
    assert client.get(f"/api/dishes/{did}",
                      headers={"Authorization": "Bearer test-token"}).json()["recipe_id"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_dish_recipe_link.py -v`
Expected: FAIL (recipe_id not returned / not persisted).

- [ ] **Step 3: Update `dishes.py`**

Add `recipe_id` to `RecipeCreate`-side handling. Change `row_to_dish`:

```python
def row_to_dish(row: sqlite3.Row) -> Dish:
    return Dish(id=row["id"], name=row["name"], tags=json.loads(row["tags"]),
                recurring_weekly=bool(row["recurring_weekly"]),
                ingredients=json.loads(row["ingredients"]),
                last_made=row["last_made"], active=bool(row["active"]),
                recipe_id=row["recipe_id"])
```

Add `recipe_id` to the `create_dish` INSERT (add `DishCreate.recipe_id` in Task 2 if not present — add it now to `DishCreate`):

```python
# in models.py class DishCreate: add after `active`
    recipe_id: int | None = None
```

Then in `create_dish`, extend the column list and values:

```python
            cur = conn.execute(
                "INSERT INTO dishes(name, tags, recurring_weekly, ingredients, active,"
                " recipe_id, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (body.name.strip(), json.dumps(body.tags, ensure_ascii=False),
                 int(body.recurring_weekly),
                 json.dumps([i.model_dump() for i in body.ingredients], ensure_ascii=False),
                 int(body.active), body.recipe_id, now, now),
            )
```

In `update_dish`, the generic loop already writes any field in `fields`; add `recipe_id` handling so it isn't JSON/int-coerced (it's a plain nullable int — the existing loop writes it as-is, which is correct). No change needed beyond ensuring `recipe_id` passes through: it falls to the default branch and is written directly. Confirm no `elif` mangles it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_dish_recipe_link.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole backend suite**

Run: `cd api && python -m pytest -q`
Expected: all pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add api/app/dishes.py api/app/models.py api/tests/test_dish_recipe_link.py
git commit -m "feat(recipes): dishes læser/skriver recipe_id"
```

---

## Task 6: Frontend types + api client methods

**Files:**
- Modify: `src/lib/api.types.ts`, `src/lib/api.ts`
- Test: `tests/recipes/api-client.test.ts`

**Interfaces:**
- Produces: `Recipe`, `RecipeInput`, `ScrapePreview` types; `Dish.recipe_id`; api methods `scrapeRecipe`, `listRecipes`, `createRecipe`, `getRecipe`, `updateRecipe`, `deleteRecipe`.

- [ ] **Step 1: Write the failing test**

```ts
// tests/recipes/api-client.test.ts
import { describe, it, expect, vi } from 'vitest';
import { makeApi } from '../../src/lib/api';

describe('recipe api methods', () => {
  it('scrapeRecipe posts url and returns preview', async () => {
    const fetchImpl = vi.fn(async () => new Response(
      JSON.stringify({ parsed: { title: 'Kødsovs', ingredients: [], steps: [] }, ok: true, image_url: null }),
      { status: 200, headers: { 'content-type': 'application/json' } }));
    const api = makeApi('http://b', 't', fetchImpl as any);
    const prev = await api.scrapeRecipe('https://x/r');
    expect(prev.parsed.title).toBe('Kødsovs');
    expect(fetchImpl).toHaveBeenCalledWith('http://b/api/recipes/scrape', expect.objectContaining({ method: 'POST' }));
  });

  it('listRecipes builds q query', async () => {
    const fetchImpl = vi.fn(async () => new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    const api = makeApi('http://b', 't', fetchImpl as any);
    await api.listRecipes('taco');
    expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/recipes?q=taco');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/recipes/api-client.test.ts`
Expected: FAIL (`api.scrapeRecipe is not a function`).

- [ ] **Step 3: Add types to `src/lib/api.types.ts`**

```ts
export interface Recipe {
	id: number;
	title: string;
	source_url: string | null;
	ingredients: Ingredient[];
	steps: string[];
	time_min: number | null;
	tags: string[];
	raw_snapshot: string;
	has_image: boolean;
	created_at: string;
	updated_at: string;
}

export interface RecipeInput {
	title: string;
	source_url?: string | null;
	ingredients?: Ingredient[];
	steps?: string[];
	time_min?: number | null;
	tags?: string[];
	raw_snapshot?: string;
	image_url?: string | null;
}

export interface ScrapePreview {
	parsed: Omit<RecipeInput, 'image_url'>;
	image_url: string | null;
	ok: boolean;
	warning?: string;
}
```

Add `recipe_id` to the existing `Dish` interface:

```ts
	recipe_id?: number | null;
```

- [ ] **Step 4: Add methods to `src/lib/api.ts`**

Add to the object returned by `makeApi` (after the inventory methods), and import the new types at the top (`Recipe, RecipeInput, ScrapePreview`):

```ts
		scrapeRecipe: (url: string) =>
			call<ScrapePreview>('/api/recipes/scrape', { method: 'POST', body: JSON.stringify({ url }) }),
		listRecipes: (q?: string) =>
			call<Recipe[]>(`/api/recipes${q ? `?q=${encodeURIComponent(q)}` : ''}`),
		getRecipe: (id: number) => call<Recipe>(`/api/recipes/${id}`),
		createRecipe: (b: RecipeInput) =>
			call<Recipe>('/api/recipes', { method: 'POST', body: JSON.stringify(b) }),
		updateRecipe: (id: number, b: Partial<RecipeInput>) =>
			call<Recipe>(`/api/recipes/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
		deleteRecipe: (id: number) => call<void>(`/api/recipes/${id}`, { method: 'DELETE' }),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run tests/recipes/api-client.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/lib/api.types.ts src/lib/api.ts tests/recipes/api-client.test.ts
git commit -m "feat(recipes): frontend-typer + api-klient-metoder"
```

---

## Task 7: BFF routes (scrape, CRUD, image proxy)

**Files:**
- Create: `src/pages/api/recipes/scrape.ts`, `src/pages/api/recipes/index.ts`, `src/pages/api/recipes/[id].ts`, `src/pages/api/recipes/[id]/image.ts`
- Test: `tests/recipes/bff.test.ts` (image proxy content-type)

**Interfaces:**
- Consumes: `getApi()`, `env.MADPLAN_API_BASE`, `env.LIFEHUB_API_TOKEN`.
- Produces: JSON endpoints for scrape/create/update/delete + a binary image proxy. All attach the Bearer server-side.

- [ ] **Step 1: Implement `src/pages/api/recipes/scrape.ts`**

```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const { url } = await request.json();
	try {
		const preview = await api.scrapeRecipe(String(url ?? ''));
		return new Response(JSON.stringify(preview), { headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'scrape' }), { status: 502, headers: { 'content-type': 'application/json' } });
	}
};
```

- [ ] **Step 2: Implement `src/pages/api/recipes/index.ts`** (create)

```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const body = await request.json();
	try {
		const recipe = await api.createRecipe(body);
		return new Response(JSON.stringify(recipe), { status: 201, headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'create' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
```

- [ ] **Step 3: Implement `src/pages/api/recipes/[id].ts`** (patch + delete)

```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const PATCH: APIRoute = async ({ request, params }) => {
	const api = await getApi();
	const body = await request.json();
	try {
		const recipe = await api.updateRecipe(Number(params.id), body);
		return new Response(JSON.stringify(recipe), { headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'update' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};

export const DELETE: APIRoute = async ({ params }) => {
	const api = await getApi();
	try {
		await api.deleteRecipe(Number(params.id));
		return new Response(null, { status: 204 });
	} catch {
		return new Response(JSON.stringify({ error: 'delete' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
```

- [ ] **Step 4: Implement `src/pages/api/recipes/[id]/image.ts`** (binary proxy — token stays server-side)

```ts
import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ params }) => {
	const { env } = await import('cloudflare:workers');
	const upstream = `${env.MADPLAN_API_BASE.replace(/\/$/, '')}/api/recipes/${Number(params.id)}/image`;
	const res = await fetch(upstream, { headers: { Authorization: `Bearer ${env.LIFEHUB_API_TOKEN}` } });
	if (!res.ok) return new Response(null, { status: 404 });
	return new Response(res.body, {
		status: 200,
		headers: {
			'content-type': res.headers.get('content-type') ?? 'application/octet-stream',
			'cache-control': 'private, max-age=86400',
		},
	});
};
```

- [ ] **Step 5: Write + run the proxy test**

```ts
// tests/recipes/bff.test.ts
import { describe, it, expect, vi } from 'vitest';

describe('image proxy', () => {
  it('passes through content-type from upstream', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new Uint8Array([255, 216, 255]), {
      status: 200, headers: { 'content-type': 'image/jpeg' } })));
    vi.doMock('cloudflare:workers', () => ({ env: { MADPLAN_API_BASE: 'http://b', LIFEHUB_API_TOKEN: 't' } }));
    const { GET } = await import('../../src/pages/api/recipes/[id]/image.ts');
    const res = await GET({ params: { id: '1' } } as any);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('image/jpeg');
  });
});
```

Run: `npx vitest run tests/recipes/bff.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pages/api/recipes/ tests/recipes/bff.test.ts
git commit -m "feat(recipes): BFF-ruter (scrape, CRUD, billed-proxy)"
```

---

## Task 8: Cookbook page `/opskrifter` (list + add with 3 modes)

**Files:**
- Create: `src/pages/opskrifter/index.astro`, `src/components/RecipeForm.astro`
- Modify: `src/components/Nav.astro`

**Interfaces:**
- Consumes: `getApi().listRecipes`, BFF `/api/recipes/scrape`, `/api/recipes`.

Follow the exact layout/markup conventions in `src/pages/beholdning.astro` (page shell, `section-head`, `cards`) and the client-script style in `src/components/QuickfillPanel.astro` (`is:inline` IIFE, `fetch` to BFF, error text into a status span).

- [ ] **Step 1: Add the nav item**

In `src/components/Nav.astro`, add to the `links` array after the `forslag` entry:

```ts
  { href: '/opskrifter', label: 'Opskrifter' },
```

- [ ] **Step 2: Create `src/components/RecipeForm.astro`**

A reusable form (title, ingredients as newline textarea, steps as newline textarea, time_min, tags, source_url, hidden raw_snapshot + image_url) that serializes to a `RecipeInput` JSON and POSTs to `/api/recipes` (create) or PATCHes `/api/recipes/{id}` (edit). Props: `{ mode: 'create' | 'edit', recipe?: Recipe }`. Ingredients text lines map to `{ name }` objects. Model the markup and inline-script on `QuickfillPanel.astro` (same escaping helper, same status-span pattern). On success, redirect to `/opskrifter/{id}` (create) or reload (edit).

- [ ] **Step 3: Create `src/pages/opskrifter/index.astro`**

Server-side: `const api = await getApi(); const q = Astro.url.searchParams.get('q') ?? ''; const recipes = await api.listRecipes(q || undefined);` inside try/catch with the standard error banner (`loadError`).

Markup:
- `<h1>Opskrifter</h1>`, a search `<form method="get">` with a text input named `q`.
- A `<details>` "Tilføj opskrift" with three tab-panels (radio-toggled): **URL** (input + "Hent" button → POST `/api/recipes/scrape` → fill a `RecipeForm` preview → confirm), **Manuel** (empty `RecipeForm`), **Indsæt tekst** (textarea → creates a recipe with `raw_snapshot` = pasted text and title from first line).
- A `cards` grid of recipe cards: thumbnail `<img src={`/api/recipes/${r.id}/image`} />` when `r.has_image`, title linking to `/opskrifter/${r.id}`, `time_min` and tags.

Inline script handles: the URL "Hent" fetch and populating the preview form; tab switching; the paste-text submit.

- [ ] **Step 4: Verify build**

Run: `npm run build`
Expected: `Complete!` with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/pages/opskrifter/index.astro src/components/RecipeForm.astro src/components/Nav.astro
git commit -m "feat(recipes): /opskrifter katalog + tilføj (URL/manuel/tekst)"
```

---

## Task 9: Recipe detail `/opskrifter/[id]` (view, snapshot, edit, dish bridges)

**Files:**
- Create: `src/pages/opskrifter/[id].astro`

**Interfaces:**
- Consumes: `getApi().getRecipe`, `getApi().listDishes`, `getApi().createDish`, `getApi().updateDish`, BFF recipe routes.

- [ ] **Step 1: Create `src/pages/opskrifter/[id].astro`**

Server-side: load `const recipe = await api.getRecipe(Number(Astro.params.id));` and `const dishes = await api.listDishes(false);` in try/catch with error banner; 404 → redirect `/opskrifter`.

Markup:
- Title, `time_min`, tags, `has_image` hero image via `/api/recipes/{id}/image`.
- Ingredients list + numbered steps (clean cooking view).
- **"Vis original"** `<details>` rendering `recipe.raw_snapshot` in a `<pre>` (escaped).
- **Redigér** toggling a `RecipeForm mode="edit"`.
- **Kilde**: link to `source_url` if present.
- **Opret ret fra opskrift** button: POST to a small inline handler that calls `createDish({ name: recipe.title, ingredients: recipe.ingredients })` then `updateDish(newId, { recipe_id: recipe.id })` — do this through a new BFF route `src/pages/api/recipes/[id]/make-dish.ts` (POST) that performs both server-side and returns the dish id. Add that route.
- **Vedhæft til ret**: a `<select>` of active dishes + button → `updateDish(dishId, { recipe_id })` via a BFF route `src/pages/api/recipes/[id]/link-dish.ts` (POST `{ dish_id }`).
- **Slet**: button → DELETE `/api/recipes/{id}` → redirect `/opskrifter`.

- [ ] **Step 2: Create the two helper BFF routes**

`src/pages/api/recipes/[id]/make-dish.ts`:

```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../../lib/api';

export const POST: APIRoute = async ({ params }) => {
	const api = await getApi();
	try {
		const recipe = await api.getRecipe(Number(params.id));
		const dish = await api.createDish({ name: recipe.title, ingredients: recipe.ingredients });
		await api.updateDish(dish.id, { recipe_id: recipe.id } as any);
		return new Response(JSON.stringify({ dish_id: dish.id }), { status: 201, headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'make-dish' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
```

`src/pages/api/recipes/[id]/link-dish.ts`:

```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../../lib/api';

export const POST: APIRoute = async ({ request, params }) => {
	const api = await getApi();
	const { dish_id } = await request.json();
	try {
		await api.updateDish(Number(dish_id), { recipe_id: Number(params.id) } as any);
		return new Response(null, { status: 204 });
	} catch {
		return new Response(JSON.stringify({ error: 'link' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
```

Note: `updateDish` accepts `Partial<DishInput>`; add `recipe_id` to `DishInput` in `src/lib/api.types.ts` so the cast isn't needed:

```ts
	recipe_id?: number | null;
```

- [ ] **Step 3: Verify build**

Run: `npm run build`
Expected: `Complete!`.

- [ ] **Step 4: Commit**

```bash
git add src/pages/opskrifter/ src/pages/api/recipes/ src/lib/api.types.ts
git commit -m "feat(recipes): opskrift-detalje + broer til retter (opret/vedhæft)"
```

---

## Task 10: Show recipe link on the meal plan

**Files:**
- Modify: `src/components/MealCard.astro`
- Test: manual build + smoke

**Interfaces:**
- Consumes: `Day.dish_id`, dishes with `recipe_id`.

- [ ] **Step 1: Read `src/components/MealCard.astro`** to find where the dish name renders.

- [ ] **Step 2: Add a recipe link**

The card receives `dishes: Dish[]`. For the day's `dish_id`, look up the dish; if it has `recipe_id`, render a small link:

```astro
{dish?.recipe_id && (
  <a class="small" href={`/opskrifter/${dish.recipe_id}`}>📖 Opskrift</a>
)}
```

Place it under the dish name, matching existing `.small` styling.

- [ ] **Step 3: Verify build + full frontend suite**

Run: `npm run build && npx vitest run`
Expected: build `Complete!`, all vitest pass.

- [ ] **Step 4: Commit**

```bash
git add src/components/MealCard.astro
git commit -m "feat(recipes): vis opskrift-link på madplanens dagskort"
```

---

## Task 11: Full verification + docs

**Files:**
- Modify: `README.md` (API table), `docs/DEPLOY.md` (recipe deploy note)

- [ ] **Step 1: Run both suites**

Run: `cd api && python -m pytest -q`  → all pass.
Run (repo root): `npx vitest run`  → all pass.
Run: `npm run build`  → `Complete!`.

- [ ] **Step 2: Add the endpoints to the README API table** (after the inventory rows)

```markdown
| POST | `/api/recipes/scrape` | Bearer | Scrape URL → preview (gemmer ikke) |
| GET/POST/PATCH/DELETE | `/api/recipes` | Bearer | Opskrifter (CRUD + cachet billede) |
| GET | `/api/recipes/{id}/image` | Bearer | Cachet billede-bytes |
```

- [ ] **Step 3: Add a deploy note to `docs/DEPLOY.md`**

Under a new `## Opskrifter` heading: backend needs the new Python deps, so LXC 103 must rebuild the image (`docker compose down && docker compose up -d --build`), then frontend `npm run build && npx wrangler deploy`. API before frontend, as always.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/DEPLOY.md
git commit -m "docs(recipes): API-tabel + deploy-note for opskrifter"
```

---

## Self-Review Notes

- **Spec coverage:** cookbook model (Tasks 1,8,9) ✓; `dishes.recipe_id` (1,2,5) ✓; structured+snapshot capture (3) ✓; image bytes cached (1,4) ✓; three input modes (8) ✓; scraping in backend (3) ✓; two dish bridges (9) ✓; fail-soft + error banners (3,4,7,8,9) ✓; token never client-side (7 image proxy) ✓; pytest+vitest (throughout) ✓; YAGNI (no scaling/inventory-push) — not implemented, correct.
- **Deps:** `recipe-scrapers`, `trafilatura` added in Task 3; backend redeploy called out (Task 11 / deploy note).
- **Type consistency:** `ScrapePreview.parsed` is `RecipeCreate` (backend) / `Omit<RecipeInput,'image_url'>` (frontend); `image_url` lives on the create body, not on `RecipeCreate` — matches `RecipeCreateBody` in Task 4 and `RecipeInput.image_url` in Task 6.
