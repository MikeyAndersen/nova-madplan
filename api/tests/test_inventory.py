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
