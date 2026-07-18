AUTH = {"Authorization": "Bearer test-token"}


def _cook(client, dish_id, date):
    r = client.put("/api/weekplan/day",
                   json={"date": date, "status": "cooked", "dish_id": dish_id},
                   headers=AUTH)
    assert r.status_code == 200


def test_stats_counts_from_history(client):
    # Isolerede navne + 2027-datoer så testen er robust mod delt test-DB.
    d1 = client.post("/api/dishes", json={"name": "Statret Alfa"}, headers=AUTH).json()["id"]
    d2 = client.post("/api/dishes", json={"name": "Statret Beta"}, headers=AUTH).json()["id"]
    _cook(client, d1, "2027-03-01")
    _cook(client, d1, "2027-03-08")
    _cook(client, d2, "2027-04-05")

    stats = client.get("/api/stats", headers=AUTH).json()
    by_id = {d["dish_id"]: d for d in stats["dishes"]}
    assert by_id[d1]["times_made"] == 2
    assert by_id[d1]["last_made"] == "2027-03-08"
    assert by_id[d2]["times_made"] == 1
    assert stats["total_cooked"] >= 3

    ids = [d["dish_id"] for d in stats["dishes"]]
    assert ids.index(d1) < ids.index(d2)  # flest-lavede først

    months = {m["month"]: m["count"] for m in stats["per_month"]}
    assert months["2027-03"] == 2 and months["2027-04"] == 1


def test_stats_response_shape(client):
    stats = client.get("/api/stats", headers=AUTH).json()
    assert set(stats) == {"total_cooked", "dishes", "per_month"}
    assert isinstance(stats["dishes"], list) and isinstance(stats["per_month"], list)
