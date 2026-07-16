# Feature B — Madplan-ejet beholdning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Madplan ejer selv beholdningen (tabel + CRUD-API), frontenden får `/beholdning` + nemlig-import, forslags-motoren scorer mod den lokale tabel, og lifehub-dashboardet viser beholdningen (kun visning).

**Architecture:** Nyt `inventory_items`-modul i FastAPI-backenden (`api/app/inventory.py` genbruges — fetch() skifter kilde fra brain-HTTP til lokal tabel; suggest.py røres IKKE). Frontenden genbruger den gamle nemlig-parser + beholdnings-/import-skærme fra `c081267`, blot med BFF-kald mod backenden i stedet for D1. Lifehub-brain poller `GET /api/inventory` med samme cache/stale-mønster som madplan-ugeplanen og viser et nyt dashboard-kort.

**Tech Stack:** FastAPI + SQLite (pytest), Astro 6 SSR på Cloudflare Workers (vitest), lifehub brain (FastAPI) + dashboard-PWA (React).

## Global Constraints

- Dokumentation dansk; kode/API/JSON-nøgler engelsk. (spec §0)
- **Rør ALDRIG:** `lifehub/brain/app/review.py`, tabellen `review_queue`, `/api/review/drain`, Vikunja-indkøbslisten, Telegram-intents, aula. (spec "Rør ALDRIG")
- Forslags-motoren: **kun kilden skifter** — `suggest.py` må ikke ændres; `inventory.fetch()` og `hash_inventory()` er de eneste motor-berøringer. (spec §4.1)
- Alle `/api/inventory`-endpoints bag Bearer `LIFEHUB_API_TOKEN`, fail-closed som resten. (spec §4.1)
- Ingen secrets i kode/klient-bundle. Frontend-login findes ikke længere — adgang gates af Cloudflare Access ved edge (commit `4bf9e01`); nye sider/BFF-ruter skal IKKE have session-kode.
- Merge-på-navn ved import: **ja** (som gammel `mergeOrInsert`), match på normaliseret `name_key`. (spec §8)
- Lokationer genbruges fra `locations.ts` (`koleskab|fryser|skab|ovrigt`) og gemmes i backend-kolonnen `category`. (spec §8)
- `best_before` udgår — den er ikke i Spec B's feltliste (§4.1); prishistorik er død (Fase 7).
- Opskrifter fra nemlig-parseren **vises kun** på bekræftelsesskærmen (info) — de indsættes ikke i ugeplanen (gammel `suggestMeal`-flow findes ikke i ny backend; retter oprettes via /retter eller quickfill).
- Commits pr. task, **ingen push** uden brugerens ok. Gælder BEGGE repos (`nova-madplan` og `../lifehub`).
- Eksisterende tests skal forblive grønne: `api/tests/test_suggest.py` hasher vikunja-formede dicts — `hash_inventory` skal derfor være form-agnostisk (kanonisk JSON pr. række), ikke bundet til nye feltnavne.
- Tests i `api/tests/` deler ÉN SQLite-fil på tværs af tests (conftest sætter DATABASE_PATH én gang). Nye inventory-tests må ikke antage tom tabel — brug unikke navne og `?q=`-filtre.

---

## File Structure

**nova-madplan backend (opret/ændr):**
- `api/app/db.py` — +`inventory_items`-tabel i `_SCHEMA`
- `api/app/models.py` — +`InventoryItemIn`, `InventoryBulkIn`, `InventoryPatch`, `InventoryItem`
- `api/app/inventory.py` — omskrives: router (CRUD/bulk) + `fetch()` mod lokal tabel + generisk `hash_inventory()`; httpx/brain-kald ud
- `api/app/main.py` — +`inventory.router`
- `api/tests/test_inventory.py` — ny

**nova-madplan frontend (opret/ændr):**
- Gendan verbatim fra `c081267`: `src/lib/nemlig/parser.ts`, `src/lib/nemlig/types.ts`, `src/lib/locations.ts`, `tests/nemlig/parser.test.ts`, `tests/locations.test.ts`
- `src/lib/api.types.ts` — +`InventoryItem`, `InventoryItemInput`
- `src/lib/api.ts` — +`listInventory`, `bulkAddInventory`, `updateInventoryItem`, `deleteInventoryItem`
- `tests/api-inventory.test.ts` — ny
- `src/components/ItemCard.astro` — gendannes tilpasset (uden best_before; +note; consume bærer quantity)
- `src/pages/beholdning.astro` — gendannes tilpasset (datakilde = API; gruppering på lokation)
- `src/pages/import.astro` — gendannes tilpasset (uden pris/best_before; opskrifter info-only)
- `src/pages/api/inventory.ts` — ny BFF-rute (add/update/consume/delete)
- `src/pages/api/import.ts` — ny BFF-rute (bulk-gem med merge-gruppering)
- `src/components/Nav.astro` — +Beholdning-link

**lifehub (ændr — separat repo `../lifehub`):**
- `brain/app/feeds/madplan.py` — +`inventory()`
- `brain/app/dashboard.py` — +`refresh_beholdning()` + `beholdning`-blok i `build()`
- `brain/app/main.py` — +scheduler-job + boot-warm
- `dashboard/src/components/widgets/Beholdning.jsx` — ny
- `dashboard/src/components/Dashboard.jsx` — wire widget
- `dashboard/src/styles/global.css` — +`.inv-*`-styles
- `dashboard/src/lib/mock.js` — +beholdning-mock

**docs:** `docs/DEPLOY.md` — Feature B-sektion.

---

## Task 1: Backend — `inventory_items`-skema + CRUD/bulk-endpoints

**Files:**
- Modify: `api/app/db.py` (`_SCHEMA`), `api/app/models.py`, `api/app/inventory.py`, `api/app/main.py`
- Test: `api/tests/test_inventory.py`

**Interfaces:**
- Produces (senere tasks afhænger af):
  - `GET /api/inventory?q=&category=` → `list[InventoryItem]` hvor `InventoryItem = {id:int, name:str, name_key:str, quantity:float, unit:str|null, note:str|null, category:str|null, source:str, added_at:str, updated_at:str}`
  - `POST /api/inventory` body `{items:[{name, quantity?, unit?, note?, category?, source?}], merge?:bool=true}` → 201 `{added:int, merged:int}`
  - `PATCH /api/inventory/{id}` (partial, `exclude_unset` som `DishUpdate`) → `InventoryItem`; 404 hvis ukendt
  - `DELETE /api/inventory/{id}` → 204; 404 hvis ukendt
  - `inventory.name_key(name:str) -> str` (lowercase, kollapset whitespace)

- [ ] **Step 1: Skriv den fejlende test**

`api/tests/test_inventory.py`:
```python
"""Feature B-accept (§4.4): inventory-CRUD, bulk+merge, auth.

NB: test-DB'en deles på tværs af tests — brug unikke navne + ?q=-filtre,
antag aldrig tom tabel."""
from conftest import AUTH


def test_inventory_requires_bearer(client):
    assert client.get("/api/inventory").status_code == 401
    assert client.get("/api/inventory", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_manual_add_list_patch_delete(client):
    body = {"items": [{"name": "Testsmør", "quantity": 2, "unit": "250 g",
                       "category": "koleskab", "note": "saltet", "source": "manuel"}]}
    resp = client.post("/api/inventory", json=body, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json() == {"added": 1, "merged": 0}

    items = client.get("/api/inventory?q=testsmør", headers=AUTH).json()
    assert len(items) == 1
    it = items[0]
    assert set(it) == {"id", "name", "name_key", "quantity", "unit", "note",
                       "category", "source", "added_at", "updated_at"}
    assert it["name"] == "Testsmør" and it["name_key"] == "testsmør"
    assert it["quantity"] == 2 and it["category"] == "koleskab" and it["note"] == "saltet"

    item_id = it["id"]
    resp = client.patch(f"/api/inventory/{item_id}", json={"quantity": 1, "note": None}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 1 and resp.json()["note"] is None
    # Partial update rører ikke resten
    assert resp.json()["unit"] == "250 g"

    assert client.delete(f"/api/inventory/{item_id}", headers=AUTH).status_code == 204
    assert client.get("/api/inventory?q=testsmør", headers=AUTH).json() == []
    assert client.patch("/api/inventory/99999", json={"quantity": 1}, headers=AUTH).status_code == 404
    assert client.delete("/api/inventory/99999", headers=AUTH).status_code == 404


def test_bulk_merge_on_name_key(client):
    client.post("/api/inventory",
                json={"items": [{"name": "Testpasta", "quantity": 1, "category": "skab",
                                 "source": "nemlig"}]}, headers=AUTH)
    resp = client.post("/api/inventory",
                       json={"items": [{"name": "  testpasta ", "quantity": 2, "source": "nemlig"},
                                       {"name": "Testris", "quantity": 1, "source": "nemlig"}],
                             "merge": True}, headers=AUTH)
    assert resp.json() == {"added": 1, "merged": 1}
    items = {i["name_key"]: i for i in client.get("/api/inventory?q=test", headers=AUTH).json()}
    assert items["testpasta"]["quantity"] == 3
    assert items["testpasta"]["category"] == "skab"  # merge lægger kun quantity til
    assert items["testris"]["quantity"] == 1


def test_bulk_no_merge_creates_duplicates(client):
    body = {"items": [{"name": "Testmælk", "quantity": 1}], "merge": False}
    client.post("/api/inventory", json=body, headers=AUTH)
    client.post("/api/inventory", json=body, headers=AUTH)
    assert len(client.get("/api/inventory?q=testmælk", headers=AUTH).json()) == 2


def test_filter_category(client):
    client.post("/api/inventory", json={"items": [
        {"name": "Testærter frost", "category": "fryser"},
        {"name": "Testærteskud", "category": "koleskab"},
    ]}, headers=AUTH)
    frys = client.get("/api/inventory?q=testærter&category=fryser", headers=AUTH).json()
    assert [i["name"] for i in frys] == ["Testærter frost"]
```

- [ ] **Step 2: Kør testen — verificér FAIL**

Kør (fra `api/`): `python -m pytest tests/test_inventory.py -v`
Forventet: FAIL — `404 Not Found` på `/api/inventory` (router findes ikke).

Brug samme venv-python som resten af projektet (lokalt: scratchpad-venv fra `.claude/skills/verify/SKILL.md`, eller `pip install -r api/requirements.txt pytest` i en ny).

- [ ] **Step 3: Tilføj tabellen i `api/app/db.py`**

I `_SCHEMA`-strengen, efter `suggestion_sets`-blokken og før indeks-linjerne, indsæt:

```sql
-- Feature B: madplan-ejet beholdning (§4.1). category = frontendens
-- lokations-slug (koleskab|fryser|skab|ovrigt), nullable.
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL,                   -- normaliseret navn til merge-på-navn
    quantity REAL NOT NULL DEFAULT 1,
    unit TEXT,
    note TEXT,
    category TEXT,
    source TEXT NOT NULL DEFAULT 'manuel',    -- nemlig | manuel
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Og blandt indeksene:
```sql
CREATE INDEX IF NOT EXISTS idx_inventory_name_key ON inventory_items(name_key);
```

`init_db()` kører `executescript` med `IF NOT EXISTS` — prod-DB'en får tabellen automatisk ved næste opstart; ingen migration nødvendig.

- [ ] **Step 4: Tilføj modeller i `api/app/models.py`**

Nederst i filen (følg filens eksisterende BaseModel/Field-stil):

```python
class InventoryItemIn(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = 1
    unit: str | None = None
    note: str | None = None
    category: str | None = None   # frontendens lokations-slug (koleskab|fryser|skab|ovrigt)
    source: str = "manuel"        # nemlig | manuel


class InventoryBulkIn(BaseModel):
    items: list[InventoryItemIn]
    merge: bool = True            # merge-på-navn: læg quantity til eksisterende (§8)


class InventoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    quantity: float | None = None
    unit: str | None = None
    note: str | None = None
    category: str | None = None


class InventoryItem(InventoryItemIn):
    id: int
    name_key: str
    added_at: str
    updated_at: str
```

- [ ] **Step 5: Skriv routeren i `api/app/inventory.py`**

Tilføj øverst i filen (behold den eksisterende `fetch()`/`hash_inventory()` urørt indtil Task 2 — de omskrives dér):

```python
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import db
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
```

NB: `config` er allerede importeret i filens eksisterende top (`from . import config`) — udvid den eksisterende import-linje til `from . import config, db` i stedet for at duplikere.

- [ ] **Step 6: Registrér routeren i `api/app/main.py`**

Udvid import-linjen og tilføj routeren (rækkefølgen blandt include_router-kaldene er ligegyldig):
```python
from . import config, db, dishes, inventory, suggest, suggestions, weekplan
...
app.include_router(inventory.router)
```

- [ ] **Step 7: Kør testene — verificér PASS + ingen regression**

Kør (fra `api/`): `python -m pytest tests/ -v`
Forventet: `test_inventory.py` 5 PASSED; alle eksisterende tests stadig grønne.

- [ ] **Step 8: Commit**

```bash
git add api/app/db.py api/app/models.py api/app/inventory.py api/app/main.py api/tests/test_inventory.py
git commit -m "Feature B: inventory_items-tabel + CRUD/bulk-endpoints (§4.1)"
```

---

## Task 2: Backend — `fetch()` mod lokal tabel + form-agnostisk hash

**Files:**
- Modify: `api/app/inventory.py` (erstat `fetch()` + `hash_inventory()`, fjern httpx/brain-kode)
- Test: `api/tests/test_inventory.py` (tilføj)

**Interfaces:**
- Consumes: `inventory_items`-tabellen fra Task 1.
- Produces: `async fetch() -> list[dict]` — rækker `{id, name, quantity, unit, note, category, source, bucket:"recently_done"}`; `hash_inventory(items) -> "sha256:..."` der ændrer sig ved enhver række-ændring. `suggest.py` kalder begge uændret.

**Baggrund:** Scoring i `suggest.py::_ingredient_hit` vægter via `item["bucket"]` — `"recently_done"` = 1.0. Alt i beholdningen ER på lager, så alle rækker får fuld vægt. `test_suggest.py::test_inventory_hash_stable_and_sensitive` hasher vikunja-formede dicts — hashen skal derfor være form-agnostisk (kanonisk JSON pr. række), så BÅDE gamle og nye former er stabile/sensitive.

- [ ] **Step 1: Tilføj den fejlende test**

Tilføj i `api/tests/test_inventory.py`:
```python
import asyncio

from app import inventory


def test_fetch_reads_local_table_and_hash_gates(client):
    client.post("/api/inventory", json={"items": [{"name": "Testhakket oksekød",
                                                   "category": "fryser"}]}, headers=AUTH)
    inv = asyncio.run(inventory.fetch())
    mine = [i for i in inv if i["name"] == "Testhakket oksekød"]
    assert len(mine) == 1
    assert mine[0]["bucket"] == "recently_done"  # fuld vægt i scoring (§4.2)
    assert mine[0]["category"] == "fryser"

    h1 = inventory.hash_inventory(inv)
    assert h1.startswith("sha256:")
    # Beholdnings-ændring → nyt hash → recompute-gate åbner (§4.4-4)
    client.post("/api/inventory", json={"items": [{"name": "Testløg", "category": "skab"}]},
                headers=AUTH)
    h2 = inventory.hash_inventory(asyncio.run(inventory.fetch()))
    assert h1 != h2
```

- [ ] **Step 2: Kør testen — verificér FAIL**

Kør (fra `api/`): `python -m pytest tests/test_inventory.py::test_fetch_reads_local_table_and_hash_gates -v`
Forventet: FAIL — gammel `fetch()` rammer brain-URL (tomt INTERNAL_API_TOKEN → returnerer `[]`, `mine` er tom).

- [ ] **Step 3: Erstat `fetch()` og `hash_inventory()` i `api/app/inventory.py`**

Slet den gamle `fetch()` (httpx/brain), den gamle `hash_inventory()`, `import httpx` og opdatér modul-docstringen. Ny kode:

```python
"""Madplan-ejet beholdning (Feature B, §4.1): CRUD-API + lager-feed til
forslags-motoren.

Kilden var før brains /api/internal/inventory (Vikunja) — nu ejer madplan selv
tabellen `inventory_items`. suggest.py er urørt: kun fetch() har skiftet kilde,
og hash_inventory() er stadig recompute-gaten (§4.1).
"""


async def fetch() -> list[dict]:
    """Lager til forslags-motoren — læser madplans egen tabel.
    `bucket: recently_done` giver fuld vægt i scoring: alt i beholdningen er
    på lager. Async-signaturen beholdes så suggest.py er urørt."""
    with db.connect() as conn:
        rows = conn.execute("SELECT id, name, quantity, unit, note, category, source"
                            " FROM inventory_items").fetchall()
    return [{**dict(r), "bucket": "recently_done"} for r in rows]


def hash_inventory(items: list[dict]) -> str:
    """sha256 over kanonisk JSON pr. række — form-agnostisk, så både gamle
    (vikunja-formede) og nye rækker hasher stabilt. Uændret hash ⇒ ingen
    recompute (§4.1)."""
    canon = sorted(json.dumps(i, ensure_ascii=False, sort_keys=True, default=str)
                   for i in items)
    digest = hashlib.sha256(json.dumps(canon, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"
```

`hashlib`/`json`-imports findes allerede. `config`-importen skal blive (bruges af `_now_iso`).

- [ ] **Step 4: Kør HELE backend-suiten — verificér PASS**

Kør (fra `api/`): `python -m pytest tests/ -v`
Forventet: alle PASSED — specielt `test_suggest.py::test_inventory_hash_stable_and_sensitive` (gamle dict-former) og `test_generate_persists_and_hash_gates` (monkeypatcher fetch) skal være grønne.

- [ ] **Step 5: Commit**

```bash
git add api/app/inventory.py api/tests/test_inventory.py
git commit -m "Feature B: forslags-motorens lager læser nu madplans egen tabel (§4.1)"
```

---

## Task 3: Frontend — gendan nemlig-parser + locations + tests (verbatim)

**Files:**
- Create (fra git-historik): `src/lib/nemlig/parser.ts`, `src/lib/nemlig/types.ts`, `src/lib/locations.ts`, `tests/nemlig/parser.test.ts`, `tests/locations.test.ts`

**Interfaces:**
- Produces: `parseNemlig(raw: string): ParseResult` med `ParseResult{items: ParsedItem[], recipes: ParsedRecipe[], unreadable: string[]}`, `ParsedItem{name, category, unit, quantity, unitPrice?, discount?, total?}`; `LOCATIONS`, `LOCATION_LABELS`, `Location`-typen, `defaultLocationForCategory(category): Location`, `isLocation(value): value is Location`.

- [ ] **Step 1: Gendan filerne verbatim**

```bash
mkdir -p src/lib/nemlig tests/nemlig
git show c081267:src/lib/nemlig/parser.ts > src/lib/nemlig/parser.ts
git show c081267:src/lib/nemlig/types.ts > src/lib/nemlig/types.ts
git show c081267:src/lib/locations.ts > src/lib/locations.ts
git show c081267:tests/nemlig/parser.test.ts > tests/nemlig/parser.test.ts
git show c081267:tests/locations.test.ts > tests/locations.test.ts
```

- [ ] **Step 2: Kør tests — verificér PASS**

Kør: `npx vitest run`
Forventet: PASS — de gendannede testfiler importerer kun parser/locations (ingen D1-afhængighed). Hvis en af dem alligevel importerer `../src/lib/db`, STOP og rapportér (det ville betyde at c081267-versionen er anderledes end antaget).

- [ ] **Step 3: Commit**

```bash
git add src/lib/nemlig src/lib/locations.ts tests/nemlig tests/locations.test.ts
git commit -m "Feature B: gendan nemlig-parser + locations fra c081267 (verbatim)"
```

---

## Task 4: Frontend — API-klientens inventory-metoder

**Files:**
- Modify: `src/lib/api.types.ts`, `src/lib/api.ts`
- Test: `tests/api-inventory.test.ts`

**Interfaces:**
- Consumes: `makeApi`-strukturen i `src/lib/api.ts` (Task 3-mønstret fra Fase 7).
- Produces: `listInventory(filter?: {q?: string; category?: string}): Promise<InventoryItem[]>`, `bulkAddInventory(items: InventoryItemInput[], merge?: boolean): Promise<{added: number; merged: number}>`, `updateInventoryItem(id: number, patch: Partial<InventoryItemInput>): Promise<InventoryItem>`, `deleteInventoryItem(id: number): Promise<void>`.

- [ ] **Step 1: Skriv den fejlende test**

`tests/api-inventory.test.ts`:
```ts
import { describe, it, expect, vi } from 'vitest';
import { makeApi } from '../src/lib/api';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

describe('makeApi inventory', () => {
	it('listInventory builds query and parses list', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse([{ id: 1, name: 'Smør' }]));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		const items = await api.listInventory({ q: 'smø', category: 'koleskab' });
		expect(items[0].name).toBe('Smør');
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/inventory?q=sm%C3%B8&category=koleskab');
	});

	it('listInventory without filter hits bare path', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse([]));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await api.listInventory();
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/inventory');
	});

	it('bulkAddInventory POSTs items+merge', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ added: 1, merged: 0 }, 201));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		const res = await api.bulkAddInventory([{ name: 'Ris' }], false);
		expect(res).toEqual({ added: 1, merged: 0 });
		const [url, init] = fetchImpl.mock.calls[0];
		expect(url).toBe('http://b/api/inventory');
		expect((init as RequestInit).method).toBe('POST');
		expect(JSON.parse((init as RequestInit).body as string)).toEqual({ items: [{ name: 'Ris' }], merge: false });
	});

	it('updateInventoryItem PATCHes; deleteInventoryItem tolerates 204', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ id: 3, quantity: 2 }));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await api.updateInventoryItem(3, { quantity: 2 });
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/inventory/3');
		expect((fetchImpl.mock.calls[0][1] as RequestInit).method).toBe('PATCH');

		const del = vi.fn(async () => new Response(null, { status: 204 }));
		const api2 = makeApi('http://b', 's', del as unknown as typeof fetch);
		await expect(api2.deleteInventoryItem(3)).resolves.toBeUndefined();
		expect((del.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
	});
});
```

- [ ] **Step 2: Kør testen — verificér FAIL**

Kør: `npx vitest run tests/api-inventory.test.ts`
Forventet: FAIL — `listInventory` findes ikke på api-objektet.

- [ ] **Step 3: Tilføj typer i `src/lib/api.types.ts`**

Nederst:
```ts
export interface InventoryItem {
	id: number;
	name: string;
	name_key: string;
	quantity: number;
	unit: string | null;
	note: string | null;
	category: string | null;
	source: string;
	added_at: string;
	updated_at: string;
}

export interface InventoryItemInput {
	name: string;
	quantity?: number;
	unit?: string | null;
	note?: string | null;
	category?: string | null;
	source?: string;
}
```

- [ ] **Step 4: Tilføj metoderne i `src/lib/api.ts`**

Udvid type-importen med `InventoryItem, InventoryItemInput`. I objektet som `makeApi` returnerer, efter `acceptSuggestion`:
```ts
		listInventory: (filter: { q?: string; category?: string } = {}) => {
			const p = new URLSearchParams();
			if (filter.q) p.set('q', filter.q);
			if (filter.category) p.set('category', filter.category);
			const qs = p.toString();
			return call<InventoryItem[]>(`/api/inventory${qs ? `?${qs}` : ''}`);
		},
		bulkAddInventory: (items: InventoryItemInput[], merge = true) =>
			call<{ added: number; merged: number }>('/api/inventory', {
				method: 'POST',
				body: JSON.stringify({ items, merge }),
			}),
		updateInventoryItem: (id: number, patch: Partial<InventoryItemInput>) =>
			call<InventoryItem>(`/api/inventory/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
		deleteInventoryItem: (id: number) => call<void>(`/api/inventory/${id}`, { method: 'DELETE' }),
```

- [ ] **Step 5: Kør tests — verificér PASS**

Kør: `npx vitest run`
Forventet: alle PASS (nye 4 + eksisterende).

- [ ] **Step 6: Commit**

```bash
git add src/lib/api.ts src/lib/api.types.ts tests/api-inventory.test.ts
git commit -m "Feature B: inventory-metoder i API-klienten"
```

---

## Task 5: Frontend — `/beholdning` + ItemCard + BFF `/api/inventory` + nav-link

**Files:**
- Create: `src/pages/api/inventory.ts`, `src/components/ItemCard.astro`, `src/pages/beholdning.astro`
- Modify: `src/components/Nav.astro`
- Reference: `git show c081267:src/pages/beholdning.astro` og `git show c081267:src/components/ItemCard.astro` (styling/struktur genbrugt; datalag + best_before/kategori-felt ændret)

**Interfaces:**
- Consumes: `getApi`, `InventoryItem` (Task 4); `LOCATIONS`, `LOCATION_LABELS`, `isLocation`, `Location` (Task 3).
- Produces: `/beholdning?q=&location=` side; BFF `POST /api/inventory` med form-actions `add|update|consume|delete`.

- [ ] **Step 1: Skriv BFF-ruten `src/pages/api/inventory.ts`**

Consume-semantik som gammel `consumeItem`: antal −1, slet ved ≤0 — formen bærer nuværende quantity.
```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
import { isLocation } from '../../lib/locations';

function s(d: FormData, k: string): string {
	return String(d.get(k) ?? '').trim();
}
function nullable(d: FormData, k: string): string | null {
	const v = s(d, k);
	return v === '' ? null : v;
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const action = s(data, 'action');
	const back = request.headers.get('referer') ?? '/beholdning';
	try {
		if (action === 'add') {
			if (!s(data, 'name')) return redirect(back);
			const category = s(data, 'category');
			await api.bulkAddInventory([{
				name: s(data, 'name'),
				quantity: Number(s(data, 'quantity')) || 1,
				unit: nullable(data, 'unit'),
				note: nullable(data, 'note'),
				category: isLocation(category) ? category : null,
				source: 'manuel',
			}], true);
		} else if (action === 'update') {
			const id = Number(s(data, 'id'));
			const category = s(data, 'category');
			if (id) {
				await api.updateInventoryItem(id, {
					name: s(data, 'name'),
					quantity: Number(s(data, 'quantity')) || 0,
					unit: nullable(data, 'unit'),
					note: nullable(data, 'note'),
					category: isLocation(category) ? category : null,
				});
			}
		} else if (action === 'consume') {
			const id = Number(s(data, 'id'));
			const qty = Number(s(data, 'quantity')) || 0;
			if (id) {
				if (qty - 1 <= 0) await api.deleteInventoryItem(id);
				else await api.updateInventoryItem(id, { quantity: qty - 1 });
			}
		} else if (action === 'delete') {
			const id = Number(s(data, 'id'));
			if (id) await api.deleteInventoryItem(id);
		}
	} catch {
		return redirect('/beholdning?error=1');
	}
	return redirect(back);
};
```

- [ ] **Step 2: Byg `src/components/ItemCard.astro`**

Gendannet struktur/styling, tilpasset: `best_before` udgår; `note` vises + kan redigeres; lokations-select skriver til `category`; consume-formen bærer quantity.
```astro
---
import type { InventoryItem } from '../lib/api.types';
import { LOCATIONS, LOCATION_LABELS, isLocation } from '../lib/locations';

interface Props {
  item: InventoryItem;
}
const { item } = Astro.props;
const qty = Number.isInteger(item.quantity) ? item.quantity : Number(item.quantity.toFixed(2));
const itemLoc = isLocation(item.category ?? '') ? item.category : 'ovrigt';
---

<div class="card">
  <div class="row spread">
    <h3>{item.name}</h3>
    <span class="qty">{qty}</span>
  </div>

  <div class="row wrap" style="gap:0.4rem; margin:0.35rem 0 0.6rem;">
    {item.unit && <span class="tag">{item.unit}</span>}
    {item.source === 'nemlig' && <span class="tag">nemlig</span>}
    {item.note && <span class="small muted">{item.note}</span>}
  </div>

  <div class="row" style="gap:0.4rem;">
    <form method="post" action="/api/inventory">
      <input type="hidden" name="action" value="consume" />
      <input type="hidden" name="id" value={item.id} />
      <input type="hidden" name="quantity" value={qty} />
      <button class="btn-sm" type="submit" title="Forbrug 1">− Forbrug</button>
    </form>

    <form method="post" action="/api/inventory" onsubmit="return confirm('Slet varen?')">
      <input type="hidden" name="action" value="delete" />
      <input type="hidden" name="id" value={item.id} />
      <button class="btn-sm btn-danger" type="submit" title="Slet">Slet</button>
    </form>
  </div>

  <details class="editor" style="margin-top:0.5rem;">
    <summary class="small">Redigér</summary>
    <form method="post" action="/api/inventory" style="margin-top:0.6rem;">
      <input type="hidden" name="action" value="update" />
      <input type="hidden" name="id" value={item.id} />
      <div class="field">
        <label>Navn</label>
        <input name="name" value={item.name} required />
      </div>
      <div class="grid-2">
        <div class="field">
          <label>Lokation</label>
          <select name="category">
            {LOCATIONS.map((l) => (
              <option value={l} selected={l === itemLoc}>{LOCATION_LABELS[l]}</option>
            ))}
          </select>
        </div>
        <div class="field">
          <label>Antal</label>
          <input name="quantity" type="number" min="0" step="1" value={qty} />
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label>Enhed</label>
          <input name="unit" value={item.unit ?? ''} placeholder="fx 500 g" />
        </div>
        <div class="field">
          <label>Note</label>
          <input name="note" value={item.note ?? ''} placeholder="fx saltet" />
        </div>
      </div>
      <button class="btn-primary btn-block" type="submit">Gem ændringer</button>
    </form>
  </details>
</div>
```

- [ ] **Step 3: Byg `src/pages/beholdning.astro`**

```astro
---
import Layout from '../components/Layout.astro';
import ItemCard from '../components/ItemCard.astro';
import { getApi, ApiError } from '../lib/api';
import { LOCATIONS, LOCATION_LABELS, isLocation, type Location } from '../lib/locations';
import type { InventoryItem } from '../lib/api.types';

const url = Astro.url;
const q = url.searchParams.get('q')?.trim() ?? '';
const locParam = url.searchParams.get('location')?.trim() ?? '';
const locFilter = isLocation(locParam) ? locParam : undefined;
const hasError = url.searchParams.get('error') === '1';

const api = await getApi();
let items: InventoryItem[] = [];
let loadError = '';
try {
  items = await api.listInventory({ q: q || undefined, category: locFilter });
} catch (e) {
  loadError = e instanceof ApiError ? `Kunne ikke hente beholdningen (${e.status}).` : 'Kunne ikke nå tjenesten.';
}

// Gruppér på lokation; ukendt/tom kategori lander i Øvrigt.
const byLoc = Object.fromEntries(LOCATIONS.map((l) => [l, []])) as Record<Location, InventoryItem[]>;
for (const it of items) byLoc[isLocation(it.category ?? '') ? (it.category as Location) : 'ovrigt'].push(it);

const sections = locFilter ? [locFilter] : LOCATIONS;
const filtering = Boolean(q || locFilter);
---

<Layout title="Beholdning">
  <h1>Beholdning</h1>
  <p class="muted small">Hvad har vi hjemme?</p>
  {hasError && <p class="notice">Handlingen kunne ikke gennemføres. Prøv igen.</p>}
  {loadError && <p class="notice">{loadError}</p>}

  <div class="row spread" style="margin-bottom:0.8rem;">
    <a class="btn btn-sm" href="/import">Importér fra nemlig →</a>
  </div>

  <form class="toolbar" method="get">
    <input type="search" name="q" value={q} placeholder="Søg vare…" aria-label="Søg" />
    <select name="location" aria-label="Lokation">
      <option value="">Alle lokationer</option>
      {LOCATIONS.map((l) => (
        <option value={l} selected={l === locFilter}>{LOCATION_LABELS[l]}</option>
      ))}
    </select>
    <button class="btn-primary" type="submit">Søg</button>
    {filtering && <a class="btn" href="/beholdning">Nulstil</a>}
  </form>

  <details class="editor" style="margin-bottom:1rem;">
    <summary class="btn btn-primary btn-block" style="text-align:center;">+ Tilføj vare manuelt</summary>
    <form method="post" action="/api/inventory" class="card" style="margin-top:0.6rem;">
      <input type="hidden" name="action" value="add" />
      <div class="field">
        <label>Navn</label>
        <input name="name" required placeholder="fx Smør" />
      </div>
      <div class="grid-2">
        <div class="field">
          <label>Lokation</label>
          <select name="category">
            {LOCATIONS.map((l) => <option value={l}>{LOCATION_LABELS[l]}</option>)}
          </select>
        </div>
        <div class="field">
          <label>Antal</label>
          <input name="quantity" type="number" min="0" step="1" value="1" />
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label>Enhed (valgfri)</label>
          <input name="unit" placeholder="fx 250 g" />
        </div>
        <div class="field">
          <label>Note (valgfri)</label>
          <input name="note" placeholder="fx saltet" />
        </div>
      </div>
      <button class="btn-primary btn-block" type="submit">Tilføj vare</button>
    </form>
  </details>

  {!loadError && sections.map((loc) => (
    <section>
      <div class="section-head">
        <h2>{LOCATION_LABELS[loc]}</h2>
        <span class="count-pill">{byLoc[loc].length} {byLoc[loc].length === 1 ? 'vare' : 'varer'}</span>
      </div>
      {byLoc[loc].length === 0 ? (
        <p class="empty">{filtering ? 'Ingen varer matcher.' : 'Tom.'}</p>
      ) : (
        <div class="cards">
          {byLoc[loc].map((it) => <ItemCard item={it} />)}
        </div>
      )}
    </section>
  ))}
</Layout>
```

- [ ] **Step 4: Tilføj nav-linket i `src/components/Nav.astro`**

I `links`-arrayet, efter Retter:
```ts
  { href: '/beholdning', label: 'Beholdning' },
```

- [ ] **Step 5: Build**

Kør: `npm run build`
Forventet: succeeds.

- [ ] **Step 6: Commit**

```bash
git add src/pages/api/inventory.ts src/components/ItemCard.astro src/pages/beholdning.astro src/components/Nav.astro
git commit -m "Feature B: /beholdning med manuel CRUD, forbrug og lokations-gruppering"
```

---

## Task 6: Frontend — `/import` (paste → parse → bekræft → gem) + BFF `/api/import`

**Files:**
- Create: `src/pages/import.astro`, `src/pages/api/import.ts`
- Reference: `git show c081267:src/pages/import.astro` (struktur genbrugt; pris/best_before/opskrift-indsættelse udgår)

**Interfaces:**
- Consumes: `parseNemlig`, `ParseResult` (Task 3); `defaultLocationForCategory`, `LOCATIONS`, `LOCATION_LABELS`, `isLocation` (Task 3); `getApi`, `bulkAddInventory`, `InventoryItemInput` (Task 4).
- Produces: `/import`-siden; BFF `POST /api/import` der bulk-gemmer og redirecter med kvitterings-params `added/merged/skipped`.

- [ ] **Step 1: Skriv BFF-ruten `src/pages/api/import.ts`**

Backend-bulk har ét merge-flag; per-vare merge-checkboxe grupperes derfor i to kald.
```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
import { isLocation } from '../../lib/locations';
import type { InventoryItemInput } from '../../lib/api.types';

function field(data: FormData, key: string): string {
	return String(data.get(key) ?? '').trim();
}
function nullableField(data: FormData, key: string): string | null {
	const v = field(data, key);
	return v === '' ? null : v;
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const included = data.getAll('include').map((v) => Number(v)).filter((n) => !Number.isNaN(n));

	const mergeItems: InventoryItemInput[] = [];
	const plainItems: InventoryItemInput[] = [];
	for (const i of included) {
		const name = field(data, `name_${i}`);
		if (!name) continue;
		const location = field(data, `location_${i}`);
		const item: InventoryItemInput = {
			name,
			quantity: Number(field(data, `quantity_${i}`)) || 1,
			unit: nullableField(data, `unit_${i}`),
			category: isLocation(location) ? location : null,
			source: 'nemlig',
		};
		(field(data, `merge_${i}`) === '1' ? mergeItems : plainItems).push(item);
	}

	let added = 0;
	let merged = 0;
	try {
		if (mergeItems.length) {
			const r = await api.bulkAddInventory(mergeItems, true);
			added += r.added;
			merged += r.merged;
		}
		if (plainItems.length) {
			const r = await api.bulkAddInventory(plainItems, false);
			added += r.added;
			merged += r.merged;
		}
	} catch {
		return redirect('/import?error=1');
	}
	const itemCount = Number(field(data, 'item_count')) || 0;
	const params = new URLSearchParams({
		added: String(added),
		merged: String(merged),
		skipped: String(Math.max(itemCount - included.length, 0)),
	});
	return redirect(`/import?${params.toString()}`);
};
```

- [ ] **Step 2: Byg `src/pages/import.astro`**

Gendannet flow: POST-til-sig-selv parser server-side (BFF); bekræftelses-skærm; gem → `/api/import`. Merge-checkbox er **checked** som default (§8: antag ja). Opskrifter vises info-only.
```astro
---
import Layout from '../components/Layout.astro';
import { parseNemlig } from '../lib/nemlig/parser';
import { defaultLocationForCategory, LOCATIONS, LOCATION_LABELS } from '../lib/locations';
import type { ParseResult } from '../lib/nemlig/types';

let parsed: ParseResult | null = null;
let rawText = '';

if (Astro.request.method === 'POST') {
  const data = await Astro.request.formData();
  rawText = String(data.get('raw') ?? '');
  if (rawText.trim()) parsed = parseNemlig(rawText);
}

// Kvittering efter indsættelse (query-params fra /api/import).
const p = Astro.url.searchParams;
const hasError = p.get('error') === '1';
const receipt = p.has('added')
  ? {
      added: Number(p.get('added') ?? 0),
      merged: Number(p.get('merged') ?? 0),
      skipped: Number(p.get('skipped') ?? 0),
    }
  : null;
---

<Layout title="Import">
  <h1>Import fra nemlig</h1>
  <p class="muted small">Indsæt en ordre — også tekst kopieret fra en faktura-PDF. Du bekræfter alt før noget gemmes.</p>

  {hasError && <p class="notice">Kunne ikke gemme varerne. Prøv igen.</p>}

  {receipt && (
    <div class="notice">
      ✅ Tilføjede {receipt.added} {receipt.added === 1 ? 'ny vare' : 'nye varer'}
      {receipt.merged > 0 && <> · lagde {receipt.merged} til eksisterende</>}
      {receipt.skipped > 0 && <> · sprang {receipt.skipped} {receipt.skipped === 1 ? 'linje' : 'linjer'} over</>}.
      <div style="margin-top:0.5rem;"><a class="btn btn-sm" href="/beholdning">Se beholdning →</a></div>
    </div>
  )}

  {!parsed && (
    <form method="post" action="/import">
      <div class="field">
        <textarea name="raw" rows="12" placeholder="Indsæt nemlig-ordre her…">{rawText}</textarea>
      </div>
      <button class="btn-primary btn-block" type="submit">Analysér</button>
    </form>
  )}

  {parsed && (
    <>
      <div class="row spread" style="margin-bottom:0.5rem;">
        <strong>{parsed.items.length} {parsed.items.length === 1 ? 'vare fundet' : 'varer fundet'}</strong>
        <a class="btn btn-sm" href="/import">Start forfra</a>
      </div>

      <form method="post" action="/api/import">
        <div class="cards" style="grid-template-columns:1fr;">
          {parsed.items.map((it, i) => {
            const loc = defaultLocationForCategory(it.category);
            return (
              <div class="card">
                <label class="row" style="gap:0.5rem; font-weight:700; margin-bottom:0.5rem;">
                  <input type="checkbox" name="include" value={i} checked style="width:auto;" />
                  Inkludér
                </label>
                <input type="hidden" name={`name_${i}`} value={it.name} />
                <div class="field">
                  <label>Vare</label>
                  <input value={it.name} disabled />
                </div>
                <div class="grid-2">
                  <div class="field">
                    <label>Antal</label>
                    <input name={`quantity_${i}`} type="number" min="1" step="1" value={it.quantity} />
                  </div>
                  <div class="field">
                    <label>Enhed</label>
                    <input name={`unit_${i}`} value={it.unit} />
                  </div>
                </div>
                <div class="grid-2">
                  <div class="field">
                    <label>Lokation</label>
                    <select name={`location_${i}`}>
                      {LOCATIONS.map((l) => (
                        <option value={l} selected={l === loc}>{LOCATION_LABELS[l]}</option>
                      ))}
                    </select>
                  </div>
                  <label class="row" style="gap:0.4rem; align-items:end; padding-bottom:0.7rem;">
                    <input type="checkbox" name={`merge_${i}`} value="1" checked style="width:auto;" />
                    <span class="small">Læg til eksisterende</span>
                  </label>
                </div>
              </div>
            );
          })}
        </div>

        <input type="hidden" name="item_count" value={parsed.items.length} />
        <button class="btn-primary btn-block" type="submit" style="margin-top:1rem;">
          Tilføj valgte varer til beholdning
        </button>
      </form>

      {parsed.recipes.length > 0 && (
        <>
          <h2>Opskrifter</h2>
          <p class="muted small">Fundet i ordren — opret dem evt. som retter under Retter.</p>
          {parsed.recipes.map((r) => (
            <div class="card" style="margin-bottom:0.6rem;">
              <strong>{r.name} <span class="tag">{r.persons} pers.</span></strong>
            </div>
          ))}
        </>
      )}

      {parsed.unreadable.length > 0 && (
        <>
          <h2>Kunne ikke læses</h2>
          <p class="muted small">Disse linjer blev sprunget over — tilføj dem evt. manuelt.</p>
          <pre class="card small" style="white-space:pre-wrap; overflow-x:auto;">{parsed.unreadable.join('\n')}</pre>
        </>
      )}
    </>
  )}
</Layout>
```

- [ ] **Step 3: Build + fuld frontend-testkørsel**

Kør: `npm run build && npx vitest run`
Forventet: build succeeds; alle tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/pages/import.astro src/pages/api/import.ts
git commit -m "Feature B: nemlig-import med parse-bekræftelse og merge-på-navn"
```

---

## Task 7: Lifehub brain — beholdnings-feed + dashboard-blok + scheduler

**⚠️ Andet repo:** alle stier er relative til `C:\Users\mikey\Documents\lifehub`. Rør IKKE `review.py`, `review_queue`, `/api/review/drain`, vikunja.py, telegram.py, aula.py.

**Files:**
- Modify: `brain/app/feeds/madplan.py`, `brain/app/dashboard.py`, `brain/app/main.py`

**Interfaces:**
- Consumes: madplans `GET /api/inventory` (Task 1) via eksisterende `MADPLAN_URL` + `LIFEHUB_API_TOKEN`.
- Produces: cache-nøglen `beholdning` (liste af items); `build()`-dokumentet får `doc["beholdning"] = {items: [...], stale: bool}` — Task 8's widget læser præcis den form.

- [ ] **Step 1: Tilføj `inventory()` i `brain/app/feeds/madplan.py`**

Efter `fetch()`:
```python
async def inventory() -> list:
    """GET madplans beholdning (Feature B §4.3). Kaster ved fejl med vilje —
    kalderen beholder seneste cache (stale-mønstret, samme som fetch())."""
    url = f"{config.MADPLAN_URL.rstrip('/')}/api/inventory"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=_headers())
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 2: Tilføj refresh-job + blok i `brain/app/dashboard.py`**

Efter `_madplan_lock = asyncio.Lock()` (linje ~21):
```python
_beholdning_lock = asyncio.Lock()
```

Efter `refresh_madplan()`:
```python
async def refresh_beholdning() -> None:
    """Poll madplans beholdning (Feature B). Ved fejl beholdes seneste cache."""
    if not madplan.enabled() or _beholdning_lock.locked():
        return
    async with _beholdning_lock:
        try:
            store.set_cache("beholdning", await madplan.inventory())
        except Exception:
            log.exception("beholdning refresh failed")
```

I `build()`, umiddelbart efter madplan-blokken (`doc["madplan"] = payload`):
```python
    # Beholdning (Feature B §4.3) — samme cache/stale-mønster som madplan.
    inv = store.get_cache_meta("beholdning")
    if inv is not None:
        items, updated_at = inv
        doc["beholdning"] = {
            "items": items,
            "stale": (time.time() - updated_at) > config.MADPLAN_STALE_MINUTES * 60,
        }
```

- [ ] **Step 3: Registrér jobbet i `brain/app/main.py`**

Efter `refresh_madplan`-jobbet i lifespan:
```python
    scheduler.add_job(dashboard.refresh_beholdning, "interval",
                      minutes=config.MADPLAN_POLL_MINUTES, jitter=30)
```
Og udvid boot-warm-tuplen med `dashboard.refresh_beholdning`:
```python
    for job in (dashboard.refresh_weather, dashboard.refresh_elpris,
                dashboard.refresh_calendar, dashboard.refresh_tasks,
                dashboard.refresh_madplan, dashboard.refresh_beholdning):
```

- [ ] **Step 4: Verificér at modulerne kan importeres (lifehub har ingen testsuite)**

Kør fra `C:\Users\mikey\Documents\lifehub\brain`:
```bash
python -m compileall app
python -c "import sys; sys.path.insert(0, '.'); from app import dashboard, main; print('imports OK')"
```
Forventet: `imports OK`. (Kan kræve `pip install -r requirements.txt` i et venv — genbrug scratchpad-venv'et og supplér med manglende pakker.) Hvis import fejler på manglende tredjeparts-pakker der ikke vedrører ændringen (fx google-libs), er `python -m compileall app` uden fejl tilstrækkeligt — notér det.

- [ ] **Step 5: Commit (i lifehub-repoet)**

```bash
cd ../lifehub
git add brain/app/feeds/madplan.py brain/app/dashboard.py brain/app/main.py
git commit -m "Feature B: beholdnings-feed fra madplan + dashboard-blok (kun visning)"
```

---

## Task 8: Lifehub PWA — Beholdning-widget

**⚠️ Andet repo:** stier relative til `C:\Users\mikey\Documents\lifehub`.

**Files:**
- Create: `dashboard/src/components/widgets/Beholdning.jsx`
- Modify: `dashboard/src/components/Dashboard.jsx`, `dashboard/src/styles/global.css`, `dashboard/src/lib/mock.js`

**Interfaces:**
- Consumes: `doc.beholdning = {items: [{id, name, quantity, unit, note, category, source, ...}], stale: bool}` (Task 7); `Card.jsx`-props `{label, meta, pulseKey, children}`.

- [ ] **Step 1: Byg `dashboard/src/components/widgets/Beholdning.jsx`**

```jsx
import Card from './Card.jsx';

const LABELS = { koleskab: 'Køleskab', fryser: 'Fryser', skab: 'Skab', ovrigt: 'Øvrigt' };
const ORDER = ['koleskab', 'fryser', 'skab', 'ovrigt'];

/* Beholdning (Feature B) — kompakt liste grupperet på lokation. Skjules helt
   når blokken mangler. `stale` = gemt kopi vist fordi madplan var utilgængelig. */
export default function Beholdning({ beholdning }) {
  if (!beholdning || !beholdning.items?.length) return null;
  const groups = {};
  for (const it of beholdning.items) {
    const key = LABELS[it.category] ? it.category : 'ovrigt';
    (groups[key] ??= []).push(it);
  }
  const meta = beholdning.stale ? <span className="card-meta">gemt kopi</span> : null;
  return (
    <Card label="Beholdning" pulseKey={JSON.stringify(beholdning.items)} meta={meta}>
      {ORDER.filter((loc) => groups[loc]?.length).map((loc) => (
        <div className="inv-group" key={loc}>
          <div className="inv-loc mono">{LABELS[loc]} · {groups[loc].length}</div>
          <div className="inv-items">
            {groups[loc].slice(0, 8).map((it) => (
              <span className="inv-item" key={it.id}>
                {it.name}{it.quantity > 1 ? ` ×${it.quantity}` : ''}
              </span>
            ))}
            {groups[loc].length > 8 && (
              <span className="inv-item inv-more">+{groups[loc].length - 8}</span>
            )}
          </div>
        </div>
      ))}
    </Card>
  );
}
```

- [ ] **Step 2: Wire i `dashboard/src/components/Dashboard.jsx`**

Import ved de øvrige widgets:
```jsx
import Beholdning from './widgets/Beholdning.jsx';
```
Render umiddelbart efter `<Ugeplan madplan={data.madplan} />`:
```jsx
        <Beholdning beholdning={data.beholdning} />
```

- [ ] **Step 3: Styles i `dashboard/src/styles/global.css`**

Efter `.wp-*`-blokken (~linje 511), i samme stil:
```css
/* Beholdning (Feature B) */
.inv-group { margin-top: 0.5rem; }
.inv-group:first-child { margin-top: 0; }
.inv-loc { font-size: 0.72rem; opacity: 0.65; margin-bottom: 0.2rem; }
.inv-items { display: flex; flex-wrap: wrap; gap: 0.3rem 0.5rem; }
.inv-item { font-size: 0.85rem; }
.inv-more { opacity: 0.55; }
```

- [ ] **Step 4: Mock-data i `dashboard/src/lib/mock.js`**

Efter `madplan`-blokken, i samme objekt:
```js
    // Feature B-beholdning: brain cacher madplans /api/inventory.
    beholdning: {
      stale: false,
      items: [
        { id: 1, name: 'Smør', quantity: 2, unit: '250 g', category: 'koleskab', source: 'nemlig' },
        { id: 2, name: 'Hakket oksekød', quantity: 1, unit: '400 g', category: 'fryser', source: 'nemlig' },
        { id: 3, name: 'Pasta', quantity: 3, unit: '500 g', category: 'skab', source: 'manuel' },
      ],
    },
```

- [ ] **Step 5: Build PWA'en**

Kør fra `C:\Users\mikey\Documents\lifehub\dashboard`:
```bash
npm ci && npm run build
```
Forventet: build succeeds.

- [ ] **Step 6: Commit (i lifehub-repoet)**

```bash
cd ../lifehub
git add dashboard/src/components/widgets/Beholdning.jsx dashboard/src/components/Dashboard.jsx dashboard/src/styles/global.css dashboard/src/lib/mock.js
git commit -m "Feature B: Beholdning-widget på dashboardet (stale-tolerant)"
```

---

## Task 9: DEPLOY.md + slutverifikation (begge repos)

**Files:**
- Modify: `docs/DEPLOY.md` (nova-madplan)

- [ ] **Step 1: Tilføj Feature B-sektion i `docs/DEPLOY.md`**

Append nederst:
```markdown
## Feature B — Beholdning (madplan-ejet)

Ingen ny infrastruktur. Rækkefølge på LXC 103:

1. **madplan-api:** `cd /opt/nova-madplan && git pull && docker compose down && docker compose up -d --build`
   (`inventory_items`-tabellen oprettes automatisk ved opstart). NB: madplans
   forslags-motor bruger ikke længere brains `/api/internal/inventory` —
   `INTERNAL_API_TOKEN` i madplans `.env` er nu ubrugt (kan blive stående).
2. **Frontend:** `npm ci && npm run build && npx wrangler deploy` (fra repo-roden
   på PC'en). Nyt menupunkt "Beholdning" + `/import`.
3. **brain:** `cd /opt/lifehub && git pull && docker compose down && docker compose up -d --build`
   (beholdnings-poll + dashboard-blok).
4. **Dashboard-PWA:** `cd /opt/lifehub/dashboard && npm ci && npm run build` og
   genudgiv `dist/` som hidtil.

Verifikation (§4.4): paste en nemlig-ordre → varer i beholdningen; tryk
Genberegn under Forslag → `inventory_hash` i svaret fra
`GET /api/suggestions/current` har skiftet; dashboard-kortet "Beholdning"
dukker op; stop madplan-api → kortet viser "gemt kopi".
```

- [ ] **Step 2: Fuld verifikation, begge repos**

```bash
# nova-madplan backend
cd api && python -m pytest tests/ -v && cd ..
# nova-madplan frontend
npx vitest run && npm run build
grep -rn "LIFEHUB_API_TOKEN" dist/client 2>/dev/null && echo "TOKEN LEAK - FAIL" || echo "NO TOKEN IN CLIENT BUNDLE"
# lifehub
cd ../lifehub/brain && python -m compileall app && cd ../dashboard && npm run build
```
Forventet: pytest alle grønne; vitest alle grønne; begge builds OK; `NO TOKEN IN CLIENT BUNDLE`.

- [ ] **Step 3: E2E-smoke via projekt-verify-skillen**

Følg `.claude/skills/verify/SKILL.md` (backend på :8400 med scratch-DB, `astro dev` på :4321, curl med `Origin`-header). Minimum:
1. `/beholdning` → 200, tomme sektioner.
2. Manuel vare: POST `/api/inventory` `action=add&name=Smør&category=koleskab&quantity=2&note=saltet` → vises under Køleskab med note.
3. `/import`: POST raw nemlig-tekst til `/import` → bekræftelses-skærm; POST bekræftelsen til `/api/import` → kvittering; varen i `/beholdning`. Testdata = `FORMAT_A` verbatim fra `tests/nemlig/parser.test.ts` (autoritativ — parseren kræver enhed + kr.-linjer):
   ```
   Drikke
   Læskedrik m. hyldeblomstsmag
   1 l
   1
   8,50 kr.
   8,50 kr.
   Frost
   Rustik baguette øko.
   350 g
   1
   19,96 kr.
   4,99 kr.
   19,96 kr.
   Køl
   Letmælk 1,5%
   1 l
   4
   10,95 kr.
   43,80 kr.
   ```
   Verificér `item_count="3"` i bekræftelses-HTML'en (grep IKKE efter varenavne — `<textarea>` ekkoer råteksten og giver falske hits).
4. Merge: gem samme vare igen med "Læg til eksisterende" → quantity summeret, ingen dublet.
5. Forbrug: `action=consume` med quantity=2 → 1 tilbage; igen → varen væk.
6. Motor-integration (§4.4-4): `POST /api/suggestions/refresh` direkte mod backenden (Bearer dev) før/efter en beholdnings-ændring → `inventory_hash` i `GET /api/suggestions/current` skifter.
7. Fejltolerance: stop backenden → `/beholdning` viser venligt banner.

- [ ] **Step 4: Commit**

```bash
git add docs/DEPLOY.md
git commit -m "Feature B: DEPLOY-guide + slutverifikation"
```

---

## Self-Review (udført)

**Spec-dækning (§4):** §4.1 tabel+endpoints → Task 1; §4.1 motor-repoint (fetch/hash, suggest.py urørt) → Task 2; §4.2 /beholdning (vis/manuel/nemlig-dump via BFF-parser) → Tasks 3, 5, 6; §4.3 lifehub-visning m. stale-fallback → Tasks 7, 8; §4.4 accept-kriterier → Task 9 Step 3 (1→smoke 3, 2→smoke 2/5, 3→Task 1-test, 4→smoke 6, 5→Task 7/8 + deploy-verifikation, 6→ingen berøring af vikunja/telegram/review — se filliste); §5 tests → Tasks 1–4; §6 deploy-tilføjelser → Task 9; §8 antagelser (locations genbrugt, merge=ja, Vikunja udenfor) → låst i Global Constraints.

**Bevidste afvigelser (dokumenteret i Global Constraints):** `best_before` udgår (ikke i §4.1's feltliste); opskrifter indsættes ikke i ugeplanen (gammelt D1-flow findes ikke; quickfill/retter dækker behovet); session-gate nævnt i §3 er erstattet af Cloudflare Access (Fase 7-beslutning, commit `4bf9e01`).

**Noter til eksekutøren:**
- Kør backend-tests fra `api/`-mappen (conftest indsætter `..` på sys.path).
- `hash_inventory` SKAL være form-agnostisk — ellers knækker `test_suggest.py`.
- Lifehub-commits sker i `../lifehub` (separat repo, egen git-historik). Ingen push af nogen af repoerne uden brugerens ok.
- Hvis et backend-endpoint opfører sig anderledes end kontrakten i en Interfaces-blok: STOP og rapportér.
