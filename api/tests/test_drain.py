"""Fase 5-accept: 32b-drain → quality=reviewed, menneske-vinder, kø-håndtering, auth."""
import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from conftest import AUTH
from test_suggest import _seed

from app import config, db, inventory, suggest
from app.weekplan import apply_day_update


def _seed_and_queue(monkeypatch):
    """Byg et 7b-sæt (og dermed en pending kø-post) for næste uge."""
    ids = _seed([(f"ret{i}", 40, False, []) for i in range(8)] + [("Fast ret", 40, True, [])])

    async def fake_fetch():
        return []
    async def fake_rank(*a, **k):
        return []
    monkeypatch.setattr(inventory, "fetch", fake_fetch)
    monkeypatch.setattr(suggest, "rank_with_llm", fake_rank)
    asyncio.run(suggest.generate(force=True))
    return ids


def test_drain_reviewed_and_human_wins(client, monkeypatch):
    ids = _seed_and_queue(monkeypatch)
    ws = suggest.next_week_start()
    locked_date = (ws + timedelta(days=1)).isoformat()   # tirsdag, låses
    with db.connect() as conn:
        apply_day_update(conn, date.fromisoformat(locked_date), "planned", ids["ret0"], None, "now")

    async def fake_strong(cands, inv, dates, today, *, model=None, url=None):
        # forsøger at ændre den låste dag (skal ignoreres) + sætte ret2 på fri dag
        return [{"date": locked_date, "dish_id": ids["ret1"], "reason": "x", "confidence": 0.9},
                {"date": dates[0], "dish_id": ids["ret2"], "reason": "y", "confidence": 0.8}]
    monkeypatch.setattr(suggest, "rank_with_llm", fake_strong)
    monkeypatch.setattr(config, "STRONG_OLLAMA_URL", "http://pc:11434")

    res = asyncio.run(suggest.drain_once())
    assert res["processed"] == 1 and res["online"] is True

    with db.connect() as conn:
        s = suggest.latest_set(conn, ws.isoformat())
        done = conn.execute("SELECT COUNT(*) FROM suggest_queue WHERE status='done'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM suggest_queue WHERE status='pending'").fetchone()[0]
    assert s["quality"] == "reviewed" and s["generated_by"] == config.STRONG_OLLAMA_MODEL
    by_date = {x["date"]: x for x in s["suggestions"]}
    assert by_date[locked_date]["dish_id"] == ids["ret0"]     # menneske-vinder: IKKE ret1
    assert done == 1 and pending == 0                          # kø-post lukket


def test_drain_offline_without_strong_url(monkeypatch):
    _seed_and_queue(monkeypatch)
    monkeypatch.setattr(config, "STRONG_OLLAMA_URL", "")
    res = asyncio.run(suggest.drain_once())
    assert res["online"] is False and res["processed"] == 0
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM suggest_queue WHERE status='pending'").fetchone()[0] == 1


def test_drain_offline_when_model_unreachable(monkeypatch):
    _seed_and_queue(monkeypatch)

    async def boom(*a, **k):
        raise RuntimeError("PC slukket")
    monkeypatch.setattr(suggest, "rank_with_llm", boom)
    monkeypatch.setattr(config, "STRONG_OLLAMA_URL", "http://pc:11434")
    res = asyncio.run(suggest.drain_once())
    assert res["online"] is False                              # 7b-sæt forbliver aktivt
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM suggest_queue WHERE status='pending'").fetchone()[0] == 1


def test_expire_stale_queue():
    _seed([("ret", 40, False, [])])   # rydder kø
    tz = ZoneInfo(config.TIMEZONE)
    recent = datetime.now(tz).isoformat(timespec="seconds")
    older = (datetime.now(tz) - timedelta(minutes=1)).isoformat(timespec="seconds")
    ancient = (datetime.now(tz) - timedelta(days=30)).isoformat(timespec="seconds")
    with db.connect() as conn:
        conn.execute("INSERT INTO suggest_queue(week_start,payload_json,status,created_at)"
                     " VALUES('2026-07-13','{}','pending',?)", (older,))    # samme uge, ældre
        conn.execute("INSERT INTO suggest_queue(week_start,payload_json,status,created_at)"
                     " VALUES('2026-07-13','{}','pending',?)", (recent,))   # samme uge, nyeste
        conn.execute("INSERT INTO suggest_queue(week_start,payload_json,status,created_at)"
                     " VALUES('2026-01-01','{}','pending',?)", (ancient,))  # > 7 dage
    with db.connect() as conn:
        suggest.expire_stale_queue(conn)
        rows = {(r["week_start"], r["created_at"]): r["status"]
                for r in conn.execute("SELECT week_start, created_at, status FROM suggest_queue")}
    assert rows[("2026-07-13", recent)] == "pending"      # nyeste pr. uge beholdes
    assert rows[("2026-07-13", older)] == "expired"       # ældre samme uge udløber
    assert rows[("2026-01-01", ancient)] == "expired"     # > 7 dage udløber


def test_drain_endpoint_auth(client, monkeypatch):
    monkeypatch.setattr(config, "MADPLAN_DRAIN_TOKEN", "")
    assert client.post("/api/drain").status_code == 403          # intet token = lukket
    monkeypatch.setattr(config, "MADPLAN_DRAIN_TOKEN", "drain-secret")
    assert client.post("/api/drain", headers={"Authorization": "Bearer nope"}).status_code == 403
    monkeypatch.setattr(config, "STRONG_OLLAMA_URL", "")
    r = client.post("/api/drain", headers={"Authorization": "Bearer drain-secret"})
    assert r.status_code == 200 and r.json()["online"] is False
