"""Engangs-migrering: gammel Cloudflare D1-dump → ny madplan.db (INTEGRATION_SPEC §8.5).

Input er en SQL-dump af den gamle D1-database:

    npx wrangler d1 export madplan --remote --output=d1_dump.sql

Mapping (gammel → ny):
  meals.title (distinkte, ikke-tomme)  → dishes (ingredients=[], tags=[],
                                          recurring_weekly=false, active=true)
  weeks + meals                        → weekplan_days (dato = start_date + weekday-1)
       dag < i dag med titel           →   status "cooked" + history-række
       dag >= i dag med titel          →   status "planned"
       is_flex uden titel              →   status "empty", note "fleks"
  meals.notes/recipe_url/cook          → foldes ind i dagens note
  dishes.last_made                     → MAX(dato) over cooked-dage pr. ret
  inventory_items, price_history       → migreres IKKE (lager ejes nu af LifeHub/Vikunja,
                                          spec A3); eksporteres til CSV ved siden af db'en.

Kørsel (lokalt eller i containeren, fra api/-mappen):

    python -m scripts.migrate_d1 --dump d1_dump.sql [--db /data/madplan.db] [--force]
"""
import argparse
import csv
import os
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, db  # noqa: E402


def load_dump(dump_path: str) -> sqlite3.Connection:
    src = sqlite3.connect(":memory:")
    src.row_factory = sqlite3.Row
    with open(dump_path, encoding="utf-8") as fh:
        src.executescript(fh.read())
    return src


def canonical_names(src: sqlite3.Connection) -> dict[str, str]:
    """lowercase-navn → hyppigste skrivemåde blandt de gamle meal-titler."""
    variants: dict[str, Counter] = {}
    for row in src.execute("SELECT title FROM meals WHERE title IS NOT NULL AND TRIM(title) != ''"):
        title = row["title"].strip()
        variants.setdefault(title.lower(), Counter())[title] += 1
    return {key: counter.most_common(1)[0][0] for key, counter in variants.items()}


def day_note(row: sqlite3.Row) -> str | None:
    parts = []
    if row["notes"] and row["notes"].strip():
        parts.append(row["notes"].strip())
    if row["recipe_url"] and row["recipe_url"].strip():
        parts.append(f"opskrift: {row['recipe_url'].strip()}")
    if row["cook"] and row["cook"].strip():
        parts.append(f"kok: {row['cook'].strip()}")
    return " · ".join(parts) or None


def export_csv(src: sqlite3.Connection, table: str, out_path: str) -> int:
    rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if rows:
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(rows[0].keys())
            writer.writerows([tuple(r) for r in rows])
    return len(rows)


def migrate(dump_path: str, today: date, force: bool) -> None:
    src = load_dump(dump_path)
    db.init_db()
    now = datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(timespec="seconds")

    with db.connect() as dst:
        existing = dst.execute("SELECT COUNT(*) FROM dishes").fetchone()[0]
        if existing and not force:
            sys.exit(f"Target db already has {existing} dishes — refusing without --force")

        names = canonical_names(src)
        dish_ids: dict[str, int] = {}
        for key, name in sorted(names.items()):
            dst.execute(
                "INSERT INTO dishes(name, tags, recurring_weekly, ingredients, active,"
                " created_at, updated_at) VALUES(?,'[]',0,'[]',1,?,?)"
                " ON CONFLICT(name) DO UPDATE SET updated_at=excluded.updated_at",
                (name, now, now),
            )
            dish_ids[key] = dst.execute(
                "SELECT id FROM dishes WHERE name = ?", (name,)).fetchone()[0]

        meals = src.execute(
            "SELECT m.*, w.start_date FROM meals m JOIN weeks w ON w.id = m.week_id"
        ).fetchall()
        planned = cooked = flex = 0
        for meal in meals:
            d = date.fromisoformat(meal["start_date"]) + timedelta(days=meal["weekday"] - 1)
            title = (meal["title"] or "").strip()
            note = day_note(meal)
            if title:
                dish_id = dish_ids[title.lower()]
                status = "cooked" if d < today else "planned"
                if status == "cooked":
                    dst.execute(
                        "INSERT OR REPLACE INTO history(date, dish_id, cooked_at) VALUES(?,?,?)",
                        (d.isoformat(), dish_id, now))
                    cooked += 1
                else:
                    planned += 1
            elif meal["is_flex"]:
                dish_id, status = None, "empty"
                note = f"fleks · {note}" if note else "fleks"
                flex += 1
            else:
                continue  # helt tom dag = ingen række (implicit empty)
            dst.execute(
                "INSERT OR REPLACE INTO weekplan_days(date, dish_id, status, note, updated_at)"
                " VALUES(?,?,?,?,?)",
                (d.isoformat(), dish_id, status, note, now))

        dst.execute("UPDATE dishes SET last_made ="
                    " (SELECT MAX(date) FROM history WHERE dish_id = dishes.id)")

        out_dir = os.path.dirname(os.path.abspath(config.DATABASE_PATH))
        n_inv = export_csv(src, "inventory_items", os.path.join(out_dir, "old_inventory_items.csv"))
        n_price = export_csv(src, "price_history", os.path.join(out_dir, "old_price_history.csv"))

    print(f"Migrated: {len(dish_ids)} dishes, {cooked} cooked days (history), "
          f"{planned} planned days, {flex} flex days.")
    print(f"Exported to CSV (not migrated): {n_inv} inventory_items, {n_price} price_history rows.")
    print(f"Target db: {config.DATABASE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dump", required=True, help="Sti til D1 SQL-dump")
    parser.add_argument("--today", default=None, help="Overstyr 'i dag' (YYYY-MM-DD) til cooked/planned-skæring")
    parser.add_argument("--force", action="store_true", help="Kør selvom target-db allerede har retter")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else datetime.now(ZoneInfo(config.TIMEZONE)).date()
    migrate(args.dump, today, args.force)
