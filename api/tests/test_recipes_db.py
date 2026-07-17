from app import db


def test_schema_has_recipe_tables_and_dish_column(client):
    with db.connect() as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "recipes" in tables
        assert "recipe_images" in tables
        dish_cols = {r["name"] for r in conn.execute("PRAGMA table_info(dishes)")}
        assert "recipe_id" in dish_cols
