from app import scrape

HTML = """<!doctype html><html><head><title>T</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Recipe",
"name":"Kødsovs","recipeIngredient":["500 g kød"],
"recipeInstructions":[{"@type":"HowToStep","text":"Brun."}],"totalTime":"PT20M",
"image":"https://x/i.jpg"}</script></head><body></body></html>"""

AUTH = {"Authorization": "Bearer test-token"}


def test_scrape_preview_then_create(client, monkeypatch):
    monkeypatch.setattr(scrape, "fetch_html", lambda url: HTML)
    r = client.post("/api/recipes/scrape", json={"url": "https://x/r"}, headers=AUTH)
    assert r.status_code == 200
    prev = r.json()
    assert prev["ok"] is True and prev["parsed"]["title"] == "Kødsovs"

    monkeypatch.setattr(scrape, "fetch_image", lambda url: (b"\xff\xd8\xff", "image/jpeg"))
    body = {**prev["parsed"], "image_url": prev["image_url"]}
    c = client.post("/api/recipes", json=body, headers=AUTH)
    assert c.status_code == 201
    rid = c.json()["id"]
    assert c.json()["has_image"] is True

    img = client.get(f"/api/recipes/{rid}/image", headers=AUTH)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


def test_create_manual_without_url(client):
    c = client.post("/api/recipes", json={"title": "Mormors frikadeller",
                    "ingredients": [{"name": "fars"}], "steps": ["Steg."]}, headers=AUTH)
    assert c.status_code == 201 and c.json()["has_image"] is False


def test_list_search_and_delete_nulls_dish_link(client):
    rid = client.post("/api/recipes", json={"title": "Tacos"}, headers=AUTH).json()["id"]
    did = client.post("/api/dishes", json={"name": "Tacos"}, headers=AUTH).json()["id"]
    client.put(f"/api/dishes/{did}", json={"recipe_id": rid}, headers=AUTH)
    assert client.get("/api/recipes?q=taco", headers=AUTH).json()[0]["id"] == rid
    assert client.delete(f"/api/recipes/{rid}", headers=AUTH).status_code == 204
    dish = client.get(f"/api/dishes/{did}", headers=AUTH).json()
    assert dish["recipe_id"] is None
