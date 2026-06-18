// Eneste datatilgangslag. UI rører aldrig D1 direkte — kald disse funktioner.
// Backend kan dermed byttes (homelab/better-sqlite3) uden at røre UI.

import type { Location } from './locations';
import { LOCATIONS } from './locations';
import { isoWeek, mondayOf, nextWeekStart, todayISO } from './dates';
import type { PriceRow } from './prices';

export interface Week {
  id: number;
  year: number;
  week_no: number;
  start_date: string;
  note: string | null;
}

export interface Meal {
  id: number;
  week_id: number;
  weekday: number; // 1=mandag … 7=søndag
  title: string | null;
  is_flex: number; // 0 | 1
  notes: string | null;
  recipe_url: string | null;
  cook: string | null;
}

export interface Item {
  id: number;
  name: string;
  location: Location;
  category: string | null;
  unit: string | null;
  quantity: number;
  added_at: string;
  best_before: string | null;
  source: string;
  note: string | null;
}

export interface NewItem {
  name: string;
  location: Location;
  category?: string | null;
  unit?: string | null;
  quantity?: number;
  best_before?: string | null;
  source?: string;
  note?: string | null;
}

// ---------- Uger & madplan ----------

async function ensureMeals(db: D1Database, weekId: number): Promise<void> {
  const stmt = db.prepare(
    'INSERT OR IGNORE INTO meals (week_id, weekday) VALUES (?, ?)',
  );
  await db.batch([1, 2, 3, 4, 5, 6, 7].map((wd) => stmt.bind(weekId, wd)));
}

export async function getOrCreateWeek(
  db: D1Database,
  year: number,
  weekNo: number,
  startDate: string,
): Promise<Week> {
  await db
    .prepare('INSERT OR IGNORE INTO weeks (year, week_no, start_date) VALUES (?, ?, ?)')
    .bind(year, weekNo, startDate)
    .run();
  const week = await db
    .prepare('SELECT * FROM weeks WHERE year = ? AND week_no = ?')
    .bind(year, weekNo)
    .first<Week>();
  if (!week) throw new Error('Kunne ikke oprette/hente uge');
  await ensureMeals(db, week.id);
  return week;
}

/** Hent den aktuelle uge (opretter den dovent hvis den mangler). */
export async function getCurrentWeek(db: D1Database): Promise<Week> {
  const today = new Date();
  const { year, week } = isoWeek(today);
  return getOrCreateWeek(db, year, week, mondayOf(today));
}

export async function getWeekWithMeals(
  db: D1Database,
  weekId: number,
): Promise<{ week: Week; meals: Meal[] }> {
  const week = await db.prepare('SELECT * FROM weeks WHERE id = ?').bind(weekId).first<Week>();
  if (!week) throw new Error('Uge ikke fundet');
  await ensureMeals(db, weekId);
  const { results } = await db
    .prepare('SELECT * FROM meals WHERE week_id = ? ORDER BY weekday')
    .bind(weekId)
    .all<Meal>();
  return { week, meals: results };
}

export async function listWeeks(db: D1Database): Promise<Week[]> {
  const { results } = await db
    .prepare('SELECT * FROM weeks ORDER BY start_date DESC')
    .all<Week>();
  return results;
}

export interface MealPatch {
  weekId: number;
  weekday: number;
  title: string | null;
  isFlex: boolean;
  notes: string | null;
  cook: string | null;
  recipeUrl: string | null;
}

export async function upsertMeal(db: D1Database, p: MealPatch): Promise<void> {
  await ensureMeals(db, p.weekId);
  await db
    .prepare(
      `UPDATE meals SET title = ?, is_flex = ?, notes = ?, cook = ?, recipe_url = ?
       WHERE week_id = ? AND weekday = ?`,
    )
    .bind(
      p.title,
      p.isFlex ? 1 : 0,
      p.notes,
      p.cook,
      p.recipeUrl,
      p.weekId,
      p.weekday,
    )
    .run();
}

/** Sæt en opskrift som forslag på en bestemt dag (uden at røre fleks/kok). */
export async function suggestMeal(
  db: D1Database,
  weekId: number,
  weekday: number,
  title: string,
): Promise<void> {
  await ensureMeals(db, weekId);
  await db
    .prepare('UPDATE meals SET title = ? WHERE week_id = ? AND weekday = ?')
    .bind(title, weekId, weekday)
    .run();
}

/** Hurtig udfyldning: sæt titler for flere dage i én uge på én gang. */
export async function setWeekTitles(
  db: D1Database,
  weekId: number,
  entries: { weekday: number; title: string }[],
): Promise<number> {
  await ensureMeals(db, weekId);
  const valid = entries.filter((e) => e.weekday >= 1 && e.weekday <= 7 && e.title);
  if (!valid.length) return 0;
  const stmt = db.prepare('UPDATE meals SET title = ? WHERE week_id = ? AND weekday = ?');
  await db.batch(valid.map((e) => stmt.bind(e.title, weekId, e.weekday)));
  return valid.length;
}

/** Skift fleks-status for en dag (opretter rækken hvis nødvendigt). */
export async function toggleFlex(
  db: D1Database,
  weekId: number,
  weekday: number,
): Promise<void> {
  await ensureMeals(db, weekId);
  await db
    .prepare(
      'UPDATE meals SET is_flex = CASE is_flex WHEN 1 THEN 0 ELSE 1 END WHERE week_id = ? AND weekday = ?',
    )
    .bind(weekId, weekday)
    .run();
}

/** Opret den næste uge efter den seneste eksisterende uge (eller efter denne uge). */
export async function createUpcomingWeek(db: D1Database): Promise<Week> {
  const latest = await db
    .prepare('SELECT start_date FROM weeks ORDER BY start_date DESC LIMIT 1')
    .first<{ start_date: string }>();
  const base = latest?.start_date ?? mondayOf(new Date());
  const { year, week, start_date } = nextWeekStart(base);
  return getOrCreateWeek(db, year, week, start_date);
}

// ---------- Beholdning ----------

export async function listInventory(
  db: D1Database,
  filter: { location?: Location; q?: string; category?: string } = {},
): Promise<Item[]> {
  const where: string[] = [];
  const binds: unknown[] = [];
  if (filter.location) {
    where.push('location = ?');
    binds.push(filter.location);
  }
  if (filter.category) {
    where.push('category = ?');
    binds.push(filter.category);
  }
  if (filter.q) {
    where.push('name LIKE ?');
    binds.push(`%${filter.q}%`);
  }
  const sql =
    'SELECT * FROM inventory_items' +
    (where.length ? ` WHERE ${where.join(' AND ')}` : '') +
    ' ORDER BY location, name COLLATE NOCASE';
  const { results } = await db.prepare(sql).bind(...binds).all<Item>();
  return results;
}

export async function addItem(db: D1Database, item: NewItem): Promise<void> {
  await db
    .prepare(
      `INSERT INTO inventory_items
         (name, location, category, unit, quantity, added_at, best_before, source, note)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      item.name,
      item.location,
      item.category ?? null,
      item.unit ?? null,
      item.quantity ?? 1,
      todayISO(),
      item.best_before ?? null,
      item.source ?? 'manuel',
      item.note ?? null,
    )
    .run();
}

export async function updateItem(
  db: D1Database,
  id: number,
  patch: Partial<Omit<Item, 'id' | 'added_at' | 'source'>>,
): Promise<void> {
  const cols: string[] = [];
  const binds: unknown[] = [];
  for (const [k, v] of Object.entries(patch)) {
    cols.push(`${k} = ?`);
    binds.push(v ?? null);
  }
  if (!cols.length) return;
  binds.push(id);
  await db.prepare(`UPDATE inventory_items SET ${cols.join(', ')} WHERE id = ?`).bind(...binds).run();
}

/** Forbrug: sænk antal med 1, slet ved 0 eller derunder. */
export async function consumeItem(db: D1Database, id: number): Promise<void> {
  const row = await db
    .prepare('SELECT quantity FROM inventory_items WHERE id = ?')
    .bind(id)
    .first<{ quantity: number }>();
  if (!row) return;
  if (row.quantity - 1 <= 0) {
    await deleteItem(db, id);
  } else {
    await db
      .prepare('UPDATE inventory_items SET quantity = quantity - 1 WHERE id = ?')
      .bind(id)
      .run();
  }
}

export async function deleteItem(db: D1Database, id: number): Promise<void> {
  await db.prepare('DELETE FROM inventory_items WHERE id = ?').bind(id).run();
}

export async function bulkInsert(db: D1Database, items: NewItem[]): Promise<number> {
  if (!items.length) return 0;
  const today = todayISO();
  const stmt = db.prepare(
    `INSERT INTO inventory_items
       (name, location, category, unit, quantity, added_at, best_before, source, note)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  );
  await db.batch(
    items.map((it) =>
      stmt.bind(
        it.name,
        it.location,
        it.category ?? null,
        it.unit ?? null,
        it.quantity ?? 1,
        today,
        it.best_before ?? null,
        it.source ?? 'nemlig',
        it.note ?? null,
      ),
    ),
  );
  return items.length;
}

/** Læg antal til en eksisterende vare i samme lokation (matcher på navn). */
export async function mergeOrInsert(db: D1Database, item: NewItem): Promise<void> {
  const existing = await db
    .prepare(
      'SELECT id, quantity FROM inventory_items WHERE name = ? AND location = ? LIMIT 1',
    )
    .bind(item.name, item.location)
    .first<{ id: number; quantity: number }>();
  if (existing) {
    await db
      .prepare('UPDATE inventory_items SET quantity = quantity + ? WHERE id = ?')
      .bind(item.quantity ?? 1, existing.id)
      .run();
  } else {
    await addItem(db, { ...item, source: item.source ?? 'nemlig' });
  }
}

export async function listCategories(db: D1Database): Promise<string[]> {
  const { results } = await db
    .prepare(
      `SELECT DISTINCT category FROM inventory_items
       WHERE category IS NOT NULL AND category <> ''
       ORDER BY category COLLATE NOCASE`,
    )
    .all<{ category: string }>();
  return results.map((r) => r.category);
}

export async function countByLocation(db: D1Database): Promise<Record<Location, number>> {
  const counts = Object.fromEntries(LOCATIONS.map((l) => [l, 0])) as Record<Location, number>;
  const { results } = await db
    .prepare('SELECT location, COUNT(*) AS c FROM inventory_items GROUP BY location')
    .all<{ location: Location; c: number }>();
  for (const r of results) {
    if (r.location in counts) counts[r.location] = r.c;
  }
  return counts;
}

// ---------- Prishistorik ----------

export async function recordPrice(
  db: D1Database,
  p: { name: string; unit: string | null; unitPrice: number; quantity?: number | null },
): Promise<void> {
  await db
    .prepare(
      'INSERT INTO price_history (name, name_key, unit, unit_price, quantity, recorded_at) VALUES (?, ?, ?, ?, ?, ?)',
    )
    .bind(
      p.name,
      p.name.trim().toLowerCase(),
      p.unit ?? null,
      p.unitPrice,
      p.quantity ?? null,
      todayISO(),
    )
    .run();
}

export async function listPrices(db: D1Database, q?: string): Promise<PriceRow[]> {
  const where = q ? ' WHERE name LIKE ?' : '';
  const binds = q ? [`%${q}%`] : [];
  const { results } = await db
    .prepare(
      `SELECT name, name_key, unit, unit_price, recorded_at FROM price_history${where}
       ORDER BY name_key, recorded_at DESC`,
    )
    .bind(...binds)
    .all<PriceRow>();
  return results;
}

export async function expiringSoon(db: D1Database, days = 3): Promise<Item[]> {
  const { results } = await db
    .prepare(
      `SELECT * FROM inventory_items
       WHERE best_before IS NOT NULL AND best_before <= date('now', '+' || ? || ' days')
       ORDER BY best_before`,
    )
    .bind(days)
    .all<Item>();
  return results;
}
