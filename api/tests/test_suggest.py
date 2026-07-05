"""Fase 4-accept: 14-dages-regel, 7b-validering/genopfyld, accept→ugeplan, hash-gating."""
import asyncio
import json
from datetime import date, timedelta

from conftest import AUTH

from app import config, db, inventory, suggest


def _seed(dishes):
    """dishes: list of (name, days_since_or_None, recurring, ingredients)."""
    today = suggest._today()
    with db.connect() as conn:
        for tbl in ("history", "weekplan_days", "suggestion_sets", "suggest_queue", "dishes"):
            conn.execute(f"DELETE FROM {tbl}")  # FK-sikker rækkefølge (børn før dishes)
        for name, ds, rec, ings in dishes:
            last = None if ds is None else (today - timedelta(days=ds)).isoformat()
            conn.execute(
                "INSERT INTO dishes(name, tags, recurring_weekly, ingredients, last_made,"
                " active, created_at, updated_at) VALUES(?,'[]',?,?,?,1,?,?)",
                (name, int(rec), json.dumps(ings), last, "now", "now"))
    with db.connect() as conn:
        return {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM dishes")}


# ── §4.3 14-dages-regel ─────────────────────────────────────────────
def test_hard_rule_excludes_recent_keeps_recurring():
    _seed([(f"gammel{i}", 40, False, []) for i in range(6)]
          + [("nylig", 3, False, []), ("fast", 2, True, [])])
    with db.connect() as conn:
        pool = suggest.candidate_pool(suggest.load_active_dishes(conn), suggest._today())
    names = {d["name"] for d in pool}
    assert "nylig" not in names            # < 14 dage udelukkes
    assert "fast" in names                 # recurring_weekly altid med
    assert len([n for n in names if n.startswith("gammel")]) == 6


def test_soften_when_pool_below_seven():
    # 4 gamle + 1 recurring = 5 hårde (<7) → blødt loft slår til (<7 dage)
    _seed([(f"gammel{i}", 40, False, []) for i in range(4)]
          + [("ti_dage", 10, False, []), ("elleve", 11, False, []),
             ("tre_dage", 3, False, []), ("fast", 2, True, [])])
    with db.connect() as conn:
        pool = suggest.candidate_pool(suggest.load_active_dishes(conn), suggest._today())
    names = {d["name"] for d in pool}
    assert "ti_dage" in names and "elleve" in names   # 7–13 dage blødt optaget
    assert "tre_dage" not in names                     # < 7 dage stadig ude


# ── §4.2 validering + genopfyldning ─────────────────────────────────
def test_assemble_validates_and_refills():
    ids = _seed([(f"ret{i}", 40, False, []) for i in range(8)] + [("fast", 40, True, [])])
    today = suggest._today()
    ws = suggest.next_week_start(today)
    dates = [(ws + timedelta(days=i)).isoformat() for i in range(7)]
    with db.connect() as conn:
        pool = suggest.candidate_pool(suggest.load_active_dishes(conn), today)
    raw = [
        {"date": dates[0], "dish_id": ids["ret2"], "reason": "x", "confidence": 0.9},
        {"date": dates[1], "dish_id": 99999, "reason": "ugyldig id"},          # dropped
        {"date": dates[1], "dish_id": ids["ret3"]},                             # fills d1
        {"date": dates[0], "dish_id": ids["ret5"]},                             # dup dato → ignoreret
    ]
    s = suggest.assemble_set(ws, pool, [], dates, raw, today)
    by_date = {x["date"]: x for x in s["suggestions"]}
    assert by_date[dates[0]]["dish_id"] == ids["ret2"]      # LLM-valg respekteret
    assert by_date[dates[1]]["dish_id"] == ids["ret3"]      # ugyldig droppet, næste brugt
    assert len(s["suggestions"]) == 7                        # genopfyldt til 7 dage
    all_ids = [x["dish_id"] for x in s["suggestions"]]
    assert all(i in {d["id"] for d in pool} for i in all_ids)   # kun kandidat-id'er
    assert len(all_ids) == len(set(all_ids))                    # ingen ret to gange
    assert ids["fast"] in all_ids                               # recurring garanteret plads
    assert all(0.0 <= x["confidence"] <= 1.0 for x in s["suggestions"])


# ── generate(): fuld pipeline + hash-gating (§4.1) ──────────────────
def test_generate_persists_and_hash_gates(monkeypatch):
    _seed([(f"ret{i}", 40, False, []) for i in range(8)])
    inv = [{"vikunja_task_id": 1, "name": "pasta", "bucket": "recently_done", "done": True}]

    async def fake_fetch():
        return inv
    async def fake_rank(cands, inventory_, dates, today):
        return []  # tving deterministisk genopfyldning
    monkeypatch.setattr(inventory, "fetch", fake_fetch)
    monkeypatch.setattr(suggest, "rank_with_llm", fake_rank)

    s = asyncio.run(suggest.generate(force=True))
    assert s is not None and len(s["suggestions"]) == 7
    assert s["quality"] == "fast" and s["inventory_hash"].startswith("sha256:")

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM suggestion_sets").fetchone()[0] == 1
        q = conn.execute("SELECT status FROM suggest_queue WHERE week_start=?",
                         (s["week_start"],)).fetchone()
        assert q["status"] == "pending"          # kø-post til 32b (Fase 5)

    # Uændret lager → force=False springer over (returnerer None)
    assert asyncio.run(suggest.generate(force=False)) is None

    # Ændret lager → nyt sæt genereres
    inv.append({"vikunja_task_id": 2, "name": "ris", "bucket": "open", "done": False})
    assert asyncio.run(suggest.generate(force=False)) is not None


def test_inventory_hash_stable_and_sensitive():
    a = [{"vikunja_task_id": 1, "name": "pasta", "bucket": "open", "done": False}]
    b = [{"vikunja_task_id": 1, "name": "pasta", "bucket": "recently_done", "done": True}]
    assert inventory.hash_inventory(a) == inventory.hash_inventory(list(a))
    assert inventory.hash_inventory(a) != inventory.hash_inventory(b)


# ── Endpoints (§3.1) ────────────────────────────────────────────────
def test_suggestions_endpoints(client, monkeypatch):
    ids = _seed([("Spaghetti bolognese", 40, False, [])])
    ws = suggest.next_week_start().isoformat()

    # current: tomt sæt før noget er genereret
    r = client.get("/api/suggestions/current", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"week_start", "generated_by", "quality", "inventory_hash",
                         "suggestions", "updated_at"}   # kontrakt 2.4
    assert body["week_start"] == ws and body["suggestions"] == []

    # refresh: 202, uden at ramme netværk (generate stubbet)
    async def noop(*a, **k):
        return None
    monkeypatch.setattr(suggest, "generate", noop)
    assert client.post("/api/suggestions/refresh", headers=AUTH).status_code == 202

    # accept: skriver forslaget ind i ugeplanen som planned
    accept_date = (suggest.next_week_start() + timedelta(days=1)).isoformat()
    r = client.post("/api/suggestions/accept",
                    json={"date": accept_date, "dish_id": ids["Spaghetti bolognese"]},
                    headers=AUTH)
    assert r.status_code == 200
    plan = r.json()
    day = next(d for d in plan["days"] if d["date"] == accept_date)
    assert day["status"] == "planned" and day["dish_id"] == ids["Spaghetti bolognese"]

    # accept af ukendt ret → 404
    assert client.post("/api/suggestions/accept",
                       json={"date": accept_date, "dish_id": 99999},
                       headers=AUTH).status_code == 404
