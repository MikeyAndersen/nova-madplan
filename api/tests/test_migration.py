"""Engangs-migrering fra gammel D1-dump (weeks/meals) til ny madplan.db."""
import os
import sqlite3
from datetime import date

from app import config
from scripts import migrate_d1

OLD_SCHEMA_AND_DATA = """
CREATE TABLE weeks (id INTEGER PRIMARY KEY, year INTEGER, week_no INTEGER,
                    start_date TEXT, note TEXT);
CREATE TABLE meals (id INTEGER PRIMARY KEY, week_id INTEGER, weekday INTEGER,
                    title TEXT, is_flex INTEGER DEFAULT 0, notes TEXT,
                    recipe_url TEXT, cook TEXT);
CREATE TABLE inventory_items (id INTEGER PRIMARY KEY, name TEXT, location TEXT,
                    category TEXT, unit TEXT, quantity REAL, added_at TEXT,
                    best_before TEXT, source TEXT, note TEXT);
CREATE TABLE price_history (id INTEGER PRIMARY KEY, name TEXT, name_key TEXT,
                    unit TEXT, unit_price REAL, quantity REAL, recorded_at TEXT);

INSERT INTO weeks VALUES (1, 2026, 26, '2026-06-22', NULL);
INSERT INTO weeks VALUES (2, 2026, 28, '2026-07-06', NULL);
-- fortid: cooked + last_made; 'kylling i karry' i to skrivemåder
INSERT INTO meals VALUES (1, 1, 1, 'kylling i karry', 0, NULL, NULL, NULL);
INSERT INTO meals VALUES (2, 1, 3, 'Kylling i karry', 0, 'ekstra ris', NULL, 'Mikey');
INSERT INTO meals VALUES (3, 1, 5, NULL, 1, NULL, NULL, NULL);
-- fremtid: planned
INSERT INTO meals VALUES (4, 2, 2, 'Pizza', 0, NULL, 'https://ex.dk/pizza', NULL);
INSERT INTO inventory_items VALUES (1, 'Mælk', 'koleskab', 'Køl', '1 l', 1, '2026-07-01', NULL, 'nemlig', NULL);
INSERT INTO price_history VALUES (1, 'Mælk', 'mælk', '1 l', 12.5, 1, '2026-07-01');
"""


def test_migrate_d1(tmp_path, monkeypatch, capsys):
    dump = tmp_path / "d1_dump.sql"
    dump.write_text(OLD_SCHEMA_AND_DATA, encoding="utf-8")
    target = tmp_path / "madplan.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(target))

    migrate_d1.migrate(str(dump), today=date(2026, 7, 4), force=False)

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row

    dishes = {r["name"]: r for r in conn.execute("SELECT * FROM dishes")}
    assert set(dishes) == {"kylling i karry", "Pizza"}  # case-dedupe, hyppigste variant vinder... 1-1 → første
    assert dishes["kylling i karry"]["last_made"] == "2026-06-24"  # onsdag i uge 26
    assert dishes["Pizza"]["last_made"] is None

    days = {r["date"]: r for r in conn.execute("SELECT * FROM weekplan_days")}
    assert days["2026-06-22"]["status"] == "cooked"
    assert days["2026-06-24"]["note"] == "ekstra ris · kok: Mikey"
    assert days["2026-06-26"]["status"] == "empty" and days["2026-06-26"]["note"] == "fleks"
    assert days["2026-07-07"]["status"] == "planned"
    assert days["2026-07-07"]["note"] == "opskrift: https://ex.dk/pizza"

    assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 2

    # gamle lager/pris-data eksporteres som CSV, ikke migreret
    out_dir = os.path.dirname(str(target))
    assert os.path.exists(os.path.join(out_dir, "old_inventory_items.csv"))
    assert os.path.exists(os.path.join(out_dir, "old_price_history.csv"))

    # idempotens-værn: nægter uden --force
    try:
        migrate_d1.migrate(str(dump), today=date(2026, 7, 4), force=False)
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass
    migrate_d1.migrate(str(dump), today=date(2026, 7, 4), force=True)  # --force må gerne
