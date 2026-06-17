-- Madplan & Beholdning — initial schema (spec §4)

-- En uge (mandag-søndag)
CREATE TABLE weeks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  year        INTEGER NOT NULL,
  week_no     INTEGER NOT NULL,          -- ISO-ugenummer
  start_date  TEXT NOT NULL,             -- mandagens dato, ISO (YYYY-MM-DD)
  note        TEXT,
  UNIQUE(year, week_no)
);

-- Én række pr. ugedag (7 pr. uge). Tom title + is_flex=0 = ikke planlagt endnu.
CREATE TABLE meals (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  week_id   INTEGER NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  weekday   INTEGER NOT NULL,            -- 1=mandag ... 7=søndag
  title     TEXT,                        -- rettens navn (NULL hvis ikke planlagt)
  is_flex   INTEGER NOT NULL DEFAULT 0,  -- 1 = fleks-ret (ingen fast plan)
  notes     TEXT,
  recipe_url TEXT,
  cook      TEXT,                        -- valgfri "hvem laver mad"
  UNIQUE(week_id, weekday)
);

-- Beholdning
CREATE TABLE inventory_items (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  location    TEXT NOT NULL,             -- 'koleskab' | 'fryser' | 'skab' | 'ovrigt'
  category    TEXT,                      -- nemlig-kategori (Køl, Frost, Grønt, ...)
  unit        TEXT,                      -- fx "500 g", "1 l", "4 stk."
  quantity    REAL NOT NULL DEFAULT 1,
  added_at    TEXT NOT NULL,             -- ISO-dato
  best_before TEXT,                      -- ISO-dato, valgfri
  source      TEXT NOT NULL DEFAULT 'manuel', -- 'manuel' | 'nemlig'
  note        TEXT
);

CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory_items(location);
CREATE INDEX IF NOT EXISTS idx_meals_week ON meals(week_id);
