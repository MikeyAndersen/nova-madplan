"""SQLite-adgang for madplan-api. Én fil (`DATABASE_PATH`), WAL, kort forbindelse pr. kald."""
import os
import sqlite3
from contextlib import contextmanager

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    tags TEXT NOT NULL DEFAULT '[]',          -- JSON-array af strenge
    recurring_weekly INTEGER NOT NULL DEFAULT 0,
    ingredients TEXT NOT NULL DEFAULT '[]',   -- JSON-array af {name, qty, unit}
    last_made TEXT,                           -- YYYY-MM-DD, vedligeholdes ud fra history
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Én række pr. dato der er sat/ændret; datoer uden række = status "empty".
CREATE TABLE IF NOT EXISTS weekplan_days (
    date TEXT PRIMARY KEY,                    -- YYYY-MM-DD
    dish_id INTEGER REFERENCES dishes(id),
    status TEXT NOT NULL DEFAULT 'empty',     -- planned | cooked | skipped | empty
    note TEXT,
    updated_at TEXT NOT NULL
);

-- Skrives når en dag markeres cooked; kilde til dishes.last_made.
CREATE TABLE IF NOT EXISTS history (
    date TEXT PRIMARY KEY,                    -- YYYY-MM-DD (kun aftensmad i v1)
    dish_id INTEGER NOT NULL REFERENCES dishes(id),
    cooked_at TEXT NOT NULL
);

-- Kø til 32b-kvalitetspasset (spec §5). Bruges først i Fase 4/5, men er med i
-- skemaet fra start jf. Fase 1-indholdet.
CREATE TABLE IF NOT EXISTS suggest_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | done | expired
    created_at TEXT NOT NULL,
    done_at TEXT
);

CREATE TABLE IF NOT EXISTS suggestion_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    payload_json TEXT NOT NULL,               -- fuldt SuggestionSet (spec 2.4)
    quality TEXT NOT NULL,                    -- fast | reviewed
    inventory_hash TEXT,
    generated_by TEXT,
    updated_at TEXT NOT NULL
);

-- Feature B: madplan-ejet beholdning (§4.1). category = frontendens
-- lokations-slug (koleskab|fryser|skab|ovrigt), nullable.
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL,                   -- normaliseret navn til merge-på-navn
    quantity REAL NOT NULL DEFAULT 1,
    unit TEXT,
    note TEXT,
    category TEXT,
    source TEXT NOT NULL DEFAULT 'manuel',    -- nemlig | manuel
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Opskrifter: scrapet + cachet. ingredients/steps/tags = JSON. raw_snapshot =
-- fuld readable sidetekst (sikkerhedsnet). image_mime sat ⇒ billede findes.
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_url TEXT,
    ingredients TEXT NOT NULL DEFAULT '[]',
    steps TEXT NOT NULL DEFAULT '[]',
    time_min INTEGER,
    tags TEXT NOT NULL DEFAULT '[]',
    raw_snapshot TEXT NOT NULL DEFAULT '',
    image_mime TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Billed-bytes adskilt så list-queries ikke trækker BLOBs. Cascade-slet med opskrift.
CREATE TABLE IF NOT EXISTS recipe_images (
    recipe_id INTEGER PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
    bytes BLOB NOT NULL,
    mime TEXT NOT NULL
);

-- Feature B: forkastede forslag pr. uge. Ekskluderes fra kandidat-pulje + prompt.
CREATE TABLE IF NOT EXISTS suggestion_rejections (
    week_start TEXT NOT NULL,
    dish_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (week_start, dish_id)
);

CREATE INDEX IF NOT EXISTS idx_history_dish ON history(dish_id);
CREATE INDEX IF NOT EXISTS idx_suggest_queue_week ON suggest_queue(week_start, status);
CREATE INDEX IF NOT EXISTS idx_suggestion_sets_week ON suggestion_sets(week_start);
CREATE INDEX IF NOT EXISTS idx_inventory_name_key ON inventory_items(name_key);
"""


def init_db() -> None:
    os.makedirs(os.path.dirname(config.DATABASE_PATH) or ".", exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(dishes)")}
        if "recipe_id" not in cols:
            conn.execute("ALTER TABLE dishes ADD COLUMN recipe_id INTEGER")


@contextmanager
def connect():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
