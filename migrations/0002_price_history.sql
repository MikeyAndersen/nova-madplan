-- Prishistorik pr. vare på tværs af nemlig-importer (spec §11)
CREATE TABLE price_history (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  name_key    TEXT NOT NULL,             -- normaliseret navn (lowercase/trimmet) til gruppering
  unit        TEXT,                      -- enhed på købstidspunktet, fx "1 l"
  unit_price  REAL NOT NULL,             -- pris pr. stk (kr.)
  quantity    REAL,                      -- antal købt
  recorded_at TEXT NOT NULL              -- ISO-dato
);

CREATE INDEX IF NOT EXISTS idx_price_history_key ON price_history(name_key);
