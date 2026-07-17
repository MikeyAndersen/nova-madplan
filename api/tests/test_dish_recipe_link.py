AUTH = {"Authorization": "Bearer test-token"}


def test_dish_carries_recipe_id(client):
    rid = client.post("/api/recipes", json={"title": "Chili"}, headers=AUTH).json()["id"]
    did = client.post("/api/dishes", json={"name": "Chili con carne", "recipe_id": rid},
                      headers=AUTH).json()["id"]
    assert client.get(f"/api/dishes/{did}", headers=AUTH).json()["recipe_id"] == rid
    client.put(f"/api/dishes/{did}", json={"recipe_id": None}, headers=AUTH)
    assert client.get(f"/api/dishes/{did}", headers=AUTH).json()["recipe_id"] is None


def test_weekplan_day_exposes_recipe_id(client):
    """Ugeplanen skal bære rettens recipe_id videre, så dashboardet kan linke
    til opskriften. null når retten ikke har en bundet opskrift."""
    # Bevidst særegne navne: test-DB'en deles på tværs af tests, så generiske
    # titler ("Tacos") ville forurene andre tests' søgninger.
    rid = client.post("/api/recipes", json={"title": "Ovnbagt laks med dild"},
                      headers=AUTH).json()["id"]
    with_recipe = client.post("/api/dishes",
                              json={"name": "Ovnbagt laks med dild", "recipe_id": rid},
                              headers=AUTH).json()["id"]
    without = client.post("/api/dishes", json={"name": "Grovboller til aften"},
                          headers=AUTH).json()["id"]

    # 2026-07-06 er en mandag; sæt onsdag med opskrift, torsdag uden.
    client.put("/api/weekplan/day", json={"date": "2026-07-08", "status": "planned",
                                          "dish_id": with_recipe}, headers=AUTH)
    client.put("/api/weekplan/day", json={"date": "2026-07-09", "status": "planned",
                                          "dish_id": without}, headers=AUTH)

    days = client.get("/api/weekplan", params={"start": "2026-07-06"},
                      headers=AUTH).json()["days"]
    assert days[2]["recipe_id"] == rid
    assert days[3]["recipe_id"] is None
