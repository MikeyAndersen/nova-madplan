from datetime import date

from app import db, suggest

AUTH = {"Authorization": "Bearer test-token"}
TODAY = date(2026, 7, 1)


def _mkdish(i, recurring=False, last=None):
    return {"id": i, "name": f"Ret {i}", "tags": [], "recurring_weekly": recurring,
            "ingredients": [], "last_made": last}


def test_candidate_pool_excludes_rejected():
    dishes = [_mkdish(i) for i in range(1, 9)]  # 8 eligible (never made)
    pool = suggest.candidate_pool(dishes, TODAY, exclude={3})
    ids = {d["id"] for d in pool}
    assert 3 not in ids and len(pool) == 7


def test_candidate_pool_relaxes_when_too_few():
    dishes = [_mkdish(i) for i in range(1, 8)]  # exactly 7
    pool = suggest.candidate_pool(dishes, TODAY, exclude={3, 4})
    ids = {d["id"] for d in pool}
    # excluding would drop to 5 < 7 → relax to keep 7 available
    assert len(pool) == 7 and 3 in ids  # rejected re-included rather than empty days


def test_build_prompt_includes_avoid_names():
    cands = [_mkdish(1)]
    prompt = suggest._build_prompt(cands, [], ["2026-07-06"], TODAY, avoid_names=["Kødsovs", "Tacos"])
    assert "Kødsovs" in prompt and "Tacos" in prompt


def test_reject_endpoint_records(client):
    did = client.post("/api/dishes", json={"name": "ForkastRet"}, headers=AUTH).json()["id"]
    assert client.post("/api/suggestions/reject", json={"dish_id": did}, headers=AUTH).status_code == 204
    ws = suggest.next_week_start().isoformat()
    with db.connect() as conn:
        assert did in suggest.rejected_ids(conn, ws)


def test_accept_clears_rejection(client):
    did = client.post("/api/dishes", json={"name": "OmbestemtRet"}, headers=AUTH).json()["id"]
    client.post("/api/suggestions/reject", json={"dish_id": did}, headers=AUTH)
    ws = suggest.next_week_start()
    a_date = ws.isoformat()
    client.post("/api/suggestions/accept", json={"date": a_date, "dish_id": did}, headers=AUTH)
    with db.connect() as conn:
        assert did not in suggest.rejected_ids(conn, ws.isoformat())


def test_reset_rejections(client):
    did = client.post("/api/dishes", json={"name": "NulstilRet"}, headers=AUTH).json()["id"]
    client.post("/api/suggestions/reject", json={"dish_id": did}, headers=AUTH)
    assert client.post("/api/suggestions/reset-rejections", headers=AUTH).status_code == 204
    ws = suggest.next_week_start().isoformat()
    with db.connect() as conn:
        assert suggest.rejected_ids(conn, ws) == set()
