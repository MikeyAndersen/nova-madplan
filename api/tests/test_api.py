"""Fase 1-accept: kontrakt 2.1/2.2, auth, cooked→history/last_made."""
from conftest import AUTH


def test_healthz_no_auth(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_requires_bearer_token(client):
    assert client.get("/api/weekplan/current").status_code == 401
    assert client.get("/api/dishes", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_dish_crud(client):
    body = {"name": "Kylling i karry", "tags": ["hverdag", "kylling"],
            "ingredients": [{"name": "kyllingebryst", "qty": 500, "unit": "g"}]}
    resp = client.post("/api/dishes", json=body, headers=AUTH)
    assert resp.status_code == 201
    dish = resp.json()
    assert set(dish) == {"id", "name", "tags", "recurring_weekly", "ingredients",
                         "last_made", "active", "recipe_id"}  # kontrakt 2.1 + recipe-link
    assert dish["last_made"] is None and dish["active"] is True

    # Duplikat (case-insensitivt) afvises
    assert client.post("/api/dishes", json={"name": "kylling i KARRY"}, headers=AUTH).status_code == 409

    dish_id = dish["id"]
    resp = client.put(f"/api/dishes/{dish_id}", json={"recurring_weekly": True}, headers=AUTH)
    assert resp.json()["recurring_weekly"] is True
    assert resp.json()["tags"] == ["hverdag", "kylling"]  # partial update rører ikke resten

    assert client.delete(f"/api/dishes/{dish_id}", headers=AUTH).status_code == 204
    assert client.get(f"/api/dishes/{dish_id}", headers=AUTH).json()["active"] is False


def test_weekplan_contract_and_cooked_flow(client):
    dish_id = client.post("/api/dishes", json={"name": "Spaghetti bolognese"}, headers=AUTH).json()["id"]

    # 2026-07-06 er en mandag
    resp = client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "planned",
                                                 "dish_id": dish_id}, headers=AUTH)
    assert resp.status_code == 200
    plan = resp.json()
    assert set(plan) == {"week_start", "days", "updated_at"}  # kontrakt 2.2
    assert plan["week_start"] == "2026-07-06"
    assert len(plan["days"]) == 7
    assert plan["days"][0]["weekday"] == "mandag"
    wed = plan["days"][2]
    assert set(wed) == {"date", "weekday", "dish_id", "dish_name", "status", "note"}
    assert wed == {"date": "2026-07-08", "weekday": "onsdag", "dish_id": dish_id,
                   "dish_name": "Spaghetti bolognese", "status": "planned", "note": None}
    assert plan["days"][3]["status"] == "empty"

    # cooked → last_made opdateres
    client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "cooked",
                                          "dish_id": dish_id}, headers=AUTH)
    assert client.get(f"/api/dishes/{dish_id}", headers=AUTH).json()["last_made"] == "2026-07-08"

    # rulles dagen tilbage til skipped, ryddes historikken igen
    client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "skipped",
                                          "dish_id": dish_id}, headers=AUTH)
    assert client.get(f"/api/dishes/{dish_id}", headers=AUTH).json()["last_made"] is None

    # vilkårlig uge + nedrunding til mandag
    plan = client.get("/api/weekplan", params={"start": "2026-07-09"}, headers=AUTH).json()
    assert plan["week_start"] == "2026-07-06"

    # valideringer
    assert client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "planned"},
                      headers=AUTH).status_code == 422
    assert client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "empty",
                                                 "dish_id": dish_id}, headers=AUTH).status_code == 422
    assert client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "planned",
                                                 "dish_id": 9999}, headers=AUTH).status_code == 404


def test_current_weekplan_is_valid(client):
    plan = client.get("/api/weekplan/current", headers=AUTH).json()
    assert len(plan["days"]) == 7
    assert plan["days"][0]["weekday"] == "mandag"
    assert plan["days"][6]["weekday"] == "søndag"
