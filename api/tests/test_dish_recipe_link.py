AUTH = {"Authorization": "Bearer test-token"}


def test_dish_carries_recipe_id(client):
    rid = client.post("/api/recipes", json={"title": "Chili"}, headers=AUTH).json()["id"]
    did = client.post("/api/dishes", json={"name": "Chili con carne", "recipe_id": rid},
                      headers=AUTH).json()["id"]
    assert client.get(f"/api/dishes/{did}", headers=AUTH).json()["recipe_id"] == rid
    client.put(f"/api/dishes/{did}", json={"recipe_id": None}, headers=AUTH)
    assert client.get(f"/api/dishes/{did}", headers=AUTH).json()["recipe_id"] is None
