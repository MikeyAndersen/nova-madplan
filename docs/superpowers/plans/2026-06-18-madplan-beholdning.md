# Madplan & Beholdning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small, closed, Danish, mobile-first web app for one household with two purposes: weekly meal plans with history, and an inventory (fridge/freezer/pantry/other) that can be filled by importing a nemlig.com order.

**Architecture:** Astro in SSR mode (`output: 'server'`) on Cloudflare Pages with the `@astrojs/cloudflare` adapter. Data lives in one Cloudflare D1 (SQLite) database bound as `DB`. A single shared password (env `SITE_PASSWORD`) gates the whole app via a signed session cookie set in middleware. All data access is isolated behind `src/lib/db.ts` so the backend could be swapped (homelab/better-sqlite3) without touching UI. The nemlig parser is a pure, dependency-free TypeScript module driven by the test fixtures in the spec.

**Tech Stack:** Astro 5, `@astrojs/cloudflare`, Cloudflare D1 + Wrangler, TypeScript (strict), vanilla JS islands, Vitest for unit tests. No UI framework, no state manager.

## Global Constraints

- Hosting: **Cloudflare Pages + D1**, target domain `madplan.nova-tech.dk`. (Deploy path is Cloudflare, **never** SFTP/One.com.)
- D1 binding name is **`DB`** everywhere (code + `wrangler.toml`).
- Password is read from env **`SITE_PASSWORD`** — **never hardcoded** in the repo or committed. Local dev value via `.dev.vars` (gitignored). Production value set as a Pages secret = `mikey`.
- One shared password = full edit access. No user accounts, no roles, no per-user tracking.
- UI language: **Danish everywhere**. Dates formatted `da-DK`, currency `kr.`.
- Mobile-first: large tappable targets; tables collapse to cards on small screens.
- Minimalism is a requirement: no onboarding, no marketing sections, discrete hover/active states only.
- Locations are exactly: `koleskab` | `fryser` | `skab` | `ovrigt` (stored as these ASCII slugs; displayed as Køleskab / Fryser / Skab / Øvrigt).
- `noindex` on every page; not linked publicly.
- No AI attribution anywhere (commits, comments, docs). Commit messages are plain Danish/English, no Co-Authored-By/Claude/Anthropic.
- Week status is **derived from dates, never stored**: historical if Sunday < today; current if today within Mon–Sun; upcoming if Monday > today.

---

## File Structure

```
nova-madplan/
├─ astro.config.mjs            # SSR + cloudflare adapter, platformProxy for local D1
├─ wrangler.toml              # Pages config: pages_build_output_dir + [[d1_databases]] DB
├─ package.json
├─ tsconfig.json
├─ .dev.vars                  # SITE_PASSWORD for local dev (GITIGNORED)
├─ .gitignore
├─ vitest.config.ts
├─ migrations/
│  └─ 0001_init.sql           # schema from spec §4
├─ src/
│  ├─ env.d.ts                # types for Astro.locals.runtime.env (DB, SITE_PASSWORD)
│  ├─ middleware.ts           # password gate: verify signed cookie, redirect to /login
│  ├─ lib/
│  │  ├─ db.ts                # ALL D1 queries (the only data-access module)
│  │  ├─ auth.ts              # cookie sign/verify (HMAC via Web Crypto), constants
│  │  ├─ dates.ts             # ISO week math, da-DK formatting, week-status derivation
│  │  ├─ locations.ts         # location slugs <-> labels, category->location mapping
│  │  └─ nemlig/
│  │     ├─ parser.ts         # parse(rawText) -> ParseResult (Format A + B + recipes)
│  │     └─ types.ts          # ParsedItem, ParsedRecipe, ParseResult types
│  ├─ components/
│  │  ├─ Nav.astro            # top nav, active link highlight
│  │  ├─ MealCard.astro       # one weekday slot (planned/flex/empty)
│  │  ├─ ItemCard.astro       # one inventory item card
│  │  └─ Layout.astro         # base HTML, noindex meta, global CSS, mobile viewport
│  ├─ styles/
│  │  └─ global.css           # design tokens, card layout, 2 accent colors
│  └─ pages/
│     ├─ login.astro          # password form (POST -> set cookie)
│     ├─ logout.ts            # clear cookie
│     ├─ index.astro          # dashboard
│     ├─ madplan/
│     │  ├─ index.astro       # current + upcoming weeks, edit days
│     │  └─ arkiv.astro       # historical weeks, read-only
│     ├─ beholdning.astro     # inventory, 4 locations, search/filter
│     ├─ import.astro         # nemlig intake: paste/upload -> preview -> confirm
│     └─ api/                 # form/JSON endpoints (POST handlers)
│        ├─ meals.ts          # upsert a meal slot, toggle flex, create upcoming week
│        ├─ inventory.ts      # add/edit/consume/delete item
│        └─ import.ts         # confirm import -> bulk insert
└─ tests/
   └─ nemlig/parser.test.ts   # fixture-driven parser tests
```

---

## Task 0: Scaffold Astro + Cloudflare adapter + tooling

**Files:**
- Create: `package.json`, `astro.config.mjs`, `tsconfig.json`, `.gitignore`, `.dev.vars`, `src/env.d.ts`, `vitest.config.ts`
- Run: `npm create astro`, `npx astro add cloudflare`

**Interfaces:**
- Produces: a buildable Astro SSR project; `Astro.locals.runtime.env.DB` (D1) and `.SITE_PASSWORD` available in dev via platformProxy.

- [ ] **Step 1: Scaffold Astro into the current (non-empty) dir**

The dir already contains `.claude/` and `docs/`. Run the official scaffold (do NOT hand-write Astro config):

```bash
npm create astro@latest . -- --template minimal --install --no-git --typescript strict --yes
```

If it refuses due to non-empty dir, scaffold into a temp subdir and move files up:
```bash
npm create astro@latest .astro-tmp -- --template minimal --install --no-git --typescript strict --yes
# then move generated files (src, package.json, astro.config.mjs, tsconfig.json, public) into repo root and delete .astro-tmp
```

- [ ] **Step 2: Add the Cloudflare adapter via the official command**

```bash
npx astro add cloudflare --yes
```

This installs the current `@astrojs/cloudflare` and wires the adapter. Read its output and confirm `astro.config.mjs` references the adapter.

- [ ] **Step 3: Set SSR + platformProxy in `astro.config.mjs`**

```js
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  output: 'server',
  adapter: cloudflare({
    platformProxy: { enabled: true }, // exposes D1 binding locally in `astro dev`
  }),
});
```

- [ ] **Step 4: Add `.gitignore` entries and `.dev.vars`**

Append to `.gitignore`:
```
.dev.vars
.wrangler/
dist/
node_modules/
.astro/
```

Create `.dev.vars` (gitignored — local dev password):
```
SITE_PASSWORD=mikey
```

- [ ] **Step 5: Type the runtime env in `src/env.d.ts`**

```ts
/// <reference types="astro/client" />
type D1Database = import('@cloudflare/workers-types').D1Database;

interface Env {
  DB: D1Database;
  SITE_PASSWORD: string;
}

type Runtime = import('@astrojs/cloudflare').Runtime<Env>;

declare namespace App {
  interface Locals extends Runtime {}
}
```

Install workers types if missing: `npm i -D @cloudflare/workers-types`.

- [ ] **Step 6: Add Vitest**

```bash
npm i -D vitest
```

Create `vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { include: ['tests/**/*.test.ts'] } });
```

Add to `package.json` scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.

- [ ] **Step 7: Verify it builds and dev server starts**

Run: `npm run build`
Expected: build succeeds (empty minimal site is fine at this point).

- [ ] **Step 8: Commit**

```bash
git init
git add -A
git commit -m "Scaffold Astro SSR + Cloudflare adapter + Vitest"
```

---

## Task 1: D1 schema + wrangler config + local migration

**Files:**
- Create: `migrations/0001_init.sql`, `wrangler.toml`

**Interfaces:**
- Produces: tables `weeks`, `meals`, `inventory_items` (exact columns from spec §4); D1 binding `DB`.

- [ ] **Step 1: Write `migrations/0001_init.sql`** — copy the schema verbatim from spec §4 (the three `CREATE TABLE` statements: `weeks`, `meals`, `inventory_items`, with the exact columns, defaults, and UNIQUE constraints). Add `CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory_items(location);` and `CREATE INDEX IF NOT EXISTS idx_meals_week ON meals(week_id);`.

- [ ] **Step 2: Create the D1 database**

```bash
wrangler d1 create madplan
```

Copy the printed `database_id` for the next step.

- [ ] **Step 3: Write `wrangler.toml`** (Pages-style)

```toml
name = "madplan"
compatibility_date = "2025-01-01"
pages_build_output_dir = "./dist"

[[d1_databases]]
binding = "DB"
database_name = "madplan"
database_id = "<id-from-step-2>"
```
(Use the actual current `compatibility_date`; confirm against wrangler output.)

- [ ] **Step 4: Apply migration to LOCAL D1**

```bash
wrangler d1 migrations apply madplan --local
```
(Or `wrangler d1 execute madplan --local --file=./migrations/0001_init.sql`.)
Expected: tables created in the local `.wrangler` D1.

- [ ] **Step 5: Verify tables exist**

```bash
wrangler d1 execute madplan --local --command "SELECT name FROM sqlite_master WHERE type='table';"
```
Expected: `weeks`, `meals`, `inventory_items` listed.

- [ ] **Step 6: Commit** — `git add migrations wrangler.toml && git commit -m "Add D1 schema and wrangler config"`
  (wrangler.toml with a `database_id` is fine to commit — it is not a secret.)

---

## Task 2: Auth — signed cookie + password gate middleware

**Files:**
- Create: `src/lib/auth.ts`, `src/middleware.ts`, `src/pages/login.astro`, `src/pages/logout.ts`
- Test: `tests/auth.test.ts`

**Interfaces:**
- Produces:
  - `auth.ts`: `signSession(secret: string): Promise<string>` returns a token `"<payload>.<hmacHex>"`; `verifySession(token: string | undefined, secret: string): Promise<boolean>`; `COOKIE_NAME = 'madplan_session'`.
  - middleware redirects unauthenticated requests (no valid cookie) to `/login` for all paths except `/login`, `/logout`, and static assets.

- [ ] **Step 1: Write failing test for sign/verify round-trip**

```ts
import { describe, it, expect } from 'vitest';
import { signSession, verifySession } from '../src/lib/auth';

describe('auth', () => {
  it('verifies a token it signed with the same secret', async () => {
    const t = await signSession('mikey');
    expect(await verifySession(t, 'mikey')).toBe(true);
  });
  it('rejects a tampered/invalid token', async () => {
    const t = await signSession('mikey');
    expect(await verifySession(t + 'x', 'mikey')).toBe(false);
    expect(await verifySession(undefined, 'mikey')).toBe(false);
    expect(await verifySession('a.b', 'mikey')).toBe(false);
  });
});
```

- [ ] **Step 2: Run test, verify it fails** — `npx vitest run tests/auth.test.ts` → FAIL (module not found).

- [ ] **Step 3: Implement `src/lib/auth.ts`** using Web Crypto HMAC-SHA256 (available in Workers + Node 26):

```ts
export const COOKIE_NAME = 'madplan_session';
const PAYLOAD = 'ok'; // static payload; secret is the password itself

async function hmacHex(message: string, secret: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function signSession(secret: string): Promise<string> {
  return `${PAYLOAD}.${await hmacHex(PAYLOAD, secret)}`;
}

export async function verifySession(token: string | undefined, secret: string): Promise<boolean> {
  if (!token) return false;
  const dot = token.lastIndexOf('.');
  if (dot < 0) return false;
  const payload = token.slice(0, dot);
  const expected = await hmacHex(payload, secret);
  // constant-time-ish compare
  const got = token.slice(dot + 1);
  if (got.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}
```

- [ ] **Step 4: Run test, verify it passes** — `npx vitest run tests/auth.test.ts` → PASS.

- [ ] **Step 5: Write `src/middleware.ts`**

```ts
import { defineMiddleware } from 'astro:middleware';
import { COOKIE_NAME, verifySession } from './lib/auth';

const PUBLIC = ['/login', '/logout'];

export const onRequest = defineMiddleware(async (ctx, next) => {
  const url = new URL(ctx.request.url);
  if (PUBLIC.includes(url.pathname) || url.pathname.startsWith('/_')) return next();
  const secret = ctx.locals.runtime.env.SITE_PASSWORD;
  const token = ctx.cookies.get(COOKIE_NAME)?.value;
  if (await verifySession(token, secret)) return next();
  return ctx.redirect('/login');
});
```

- [ ] **Step 6: Write `src/pages/login.astro`** — danish password form; on POST, compare `formData.password` to `SITE_PASSWORD`, set signed cookie (`httpOnly`, `sameSite:'lax'`, `secure`, `path:'/'`, ~30 day maxAge), redirect to `/`. On wrong password show "Forkert kodeord". Use `Astro.locals.runtime.env.SITE_PASSWORD`.

- [ ] **Step 7: Write `src/pages/logout.ts`** — delete cookie, redirect to `/login`.

- [ ] **Step 8: Manual verify** — `npm run dev`, hit `/` → redirected to `/login`; wrong password rejected; `mikey` logs in and lands on `/`.

- [ ] **Step 9: Commit** — `git add -A && git commit -m "Add shared-password gate with signed session cookie"`

---

## Task 3: Helpers — dates, locations, category mapping

**Files:**
- Create: `src/lib/dates.ts`, `src/lib/locations.ts`
- Test: `tests/dates.test.ts`, `tests/locations.test.ts`

**Interfaces:**
- Produces:
  - `dates.ts`: `isoWeek(d: Date): { year: number; week: number }`; `mondayOf(d: Date): string` (ISO YYYY-MM-DD of Monday); `weekStatus(startDateISO: string, today?: Date): 'historisk'|'nuvaerende'|'kommende'`; `formatDa(iso: string): string` (e.g. "tirsdag 18. jun"); `WEEKDAYS_DA = ['Mandag',...,'Søndag']`; `nextWeekStart(fromISO: string): { year, week, start_date }`.
  - `locations.ts`: `LOCATIONS = ['koleskab','fryser','skab','ovrigt'] as const`; `LOCATION_LABELS: Record<Location,string>`; `defaultLocationForCategory(category: string): Location` implementing spec §6.6.

- [ ] **Step 1: Write failing tests**

```ts
// tests/dates.test.ts
import { describe, it, expect } from 'vitest';
import { weekStatus, mondayOf, isoWeek } from '../src/lib/dates';
describe('dates', () => {
  it('derives week status from dates', () => {
    // start_date is a Monday; today fixed
    expect(weekStatus('2026-06-15', new Date('2026-06-18'))).toBe('nuvaerende'); // Mon 15 - Sun 21
    expect(weekStatus('2026-06-08', new Date('2026-06-18'))).toBe('historisk');  // ended Sun 14
    expect(weekStatus('2026-06-22', new Date('2026-06-18'))).toBe('kommende');
  });
  it('mondayOf returns the Monday of the week', () => {
    expect(mondayOf(new Date('2026-06-18'))).toBe('2026-06-15');
  });
  it('isoWeek gives ISO year/week', () => {
    expect(isoWeek(new Date('2026-06-18'))).toEqual({ year: 2026, week: 25 });
  });
});
```
```ts
// tests/locations.test.ts
import { describe, it, expect } from 'vitest';
import { defaultLocationForCategory } from '../src/lib/locations';
describe('category->location', () => {
  it('maps per spec', () => {
    expect(defaultLocationForCategory('Frost')).toBe('fryser');
    expect(defaultLocationForCategory('Køl')).toBe('koleskab');
    expect(defaultLocationForCategory('Mejeri')).toBe('koleskab');
    expect(defaultLocationForCategory('Kød & fisk')).toBe('koleskab');
    expect(defaultLocationForCategory('Grønt')).toBe('koleskab');
    expect(defaultLocationForCategory('Kolonial')).toBe('skab');
    expect(defaultLocationForCategory('Brød')).toBe('skab');
    expect(defaultLocationForCategory('Drikke')).toBe('skab');
    expect(defaultLocationForCategory('Pleje')).toBe('ovrigt');
    expect(defaultLocationForCategory('Ukendt')).toBe('skab'); // fallback
  });
});
```

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement `dates.ts`** — ISO week via the standard Thursday algorithm; `mondayOf` by shifting to ISO Monday; `weekStatus` computes Sunday = Monday+6 and compares to `today` (date-only, no time). `formatDa` uses `new Intl.DateTimeFormat('da-DK', ...)`.

- [ ] **Step 4: Implement `locations.ts`** — the mapping object and `defaultLocationForCategory` (case-insensitive match on the keys above; default `'skab'`). Note: subtype refinements (Grønt rodfrugter→Skab, frost-marked Kød→Fryser, Drikke kølevarer→Køleskab) are *user-overridable defaults*, so the base mapping uses the table's primary default; the import preview lets the user override per row.

- [ ] **Step 5: Run tests, verify they pass.**

- [ ] **Step 6: Commit** — `git commit -am "Add date/week and location/category helpers"`

---

## Task 4: Nemlig parser (TDD core) — Format A, Format B, recipes

**Files:**
- Create: `src/lib/nemlig/types.ts`, `src/lib/nemlig/parser.ts`
- Test: `tests/nemlig/parser.test.ts`

**Interfaces:**
- Produces in `types.ts`:
```ts
export interface ParsedItem {
  name: string;
  category: string;      // nemlig category header or '' if unknown
  unit: string;          // e.g. "1 l", "350 g", "4 stk."
  quantity: number;      // integer count
  unitPrice?: number;    // kr per stk
  discount?: number;     // kr, optional
  total?: number;        // kr line total
}
export interface ParsedRecipe { name: string; persons: number; }
export interface ParseResult {
  items: ParsedItem[];
  recipes: ParsedRecipe[];
  unreadable: string[];  // lines that couldn't be parsed
}
```
- `parser.ts`: `export function parseNemlig(raw: string): ParseResult` — auto-detects Format A (vertical) vs Format B (columns) per the spec, ignores footer/total lines (§6.4), and separates recipe lines (§6.5).

- [ ] **Step 1: Write failing fixture tests** using the spec's BILAG fixtures.

```ts
import { describe, it, expect } from 'vitest';
import { parseNemlig } from '../../src/lib/nemlig/parser';

const FORMAT_A = `Drikke
Læskedrik m. hyldeblomstsmag
1 l
1
8,50 kr.
8,50 kr.
Frost
Rustik baguette øko.
350 g
1
19,96 kr.
4,99 kr.
19,96 kr.
Køl
Letmælk 1,5%
1 l
4
10,95 kr.
43,80 kr.`;

const FORMAT_B = `Letmælk 1,5% 1 l 10,95 4 43,80
Mascarpone 250 g 8,24 24,71 1 24,71
Rustik baguette øko. 350 g 4,99 19,96 1 19,96
Cremet pasta med salsiccia 4 personer 0 0,00
Varer i alt kr. 888,48
Total (heraf 25% moms kr. 188,06) kr. 940,28`;

describe('Format A — vertical', () => {
  const r = parseNemlig(FORMAT_A);
  it('parses 3 items with names, units, quantities', () => {
    expect(r.items.map(i => i.name)).toEqual([
      'Læskedrik m. hyldeblomstsmag', 'Rustik baguette øko.', 'Letmælk 1,5%',
    ]);
  });
  it('assigns categories from headers', () => {
    expect(r.items.map(i => i.category)).toEqual(['Drikke', 'Frost', 'Køl']);
  });
  it('parses unit + quantity', () => {
    expect(r.items[2]).toMatchObject({ unit: '1 l', quantity: 4, total: 43.8 });
  });
  it('handles the optional discount line (3 kr-lines = stk,rabat,total)', () => {
    expect(r.items[1]).toMatchObject({ unitPrice: 4.99, discount: undefined, total: 19.96 });
    // baguette: 19,96 / 4,99 / 19,96 -> stk=19,96? per spec: last=total, first=stk, middle=rabat
  });
});

describe('Format B — columns', () => {
  const r = parseNemlig(FORMAT_B);
  it('parses 3 inventory items (recipe + totals excluded)', () => {
    expect(r.items.map(i => i.name)).toEqual(['Letmælk 1,5%', 'Mascarpone', 'Rustik baguette øko.']);
  });
  it('extracts unit and integer quantity before price', () => {
    expect(r.items[0]).toMatchObject({ unit: '1 l', quantity: 4, total: 43.8 });
    expect(r.items[1]).toMatchObject({ unit: '250 g', quantity: 1, total: 24.71 });
  });
  it('captures recipe lines separately', () => {
    expect(r.recipes).toEqual([{ name: 'Cremet pasta med salsiccia', persons: 4 }]);
  });
  it('ignores footer/total lines', () => {
    expect(r.items.find(i => /Varer i alt|Total/.test(i.name))).toBeUndefined();
  });
});
```
(Note: resolve the baguette §6.2 discount example precisely while implementing — the rule is: of the trailing kr-lines, **last = total, first = stk-price, middle (if 3) = discount**. Adjust the assertion to the spec's literal rule, not a guess.)

- [ ] **Step 2: Run tests, verify they fail** — `npx vitest run tests/nemlig` → FAIL.

- [ ] **Step 3: Implement `types.ts`** (the interfaces above).

- [ ] **Step 4: Implement format detection + shared helpers in `parser.ts`**
  - `KNOWN_CATEGORIES = ['Drikke','Frost','Grønt','Kolonial','Kød & fisk','Køl','Mejeri','Brød','Pleje']`.
  - `IGNORE` set/regex for §6.4 footer lines (`Varer i alt`, `Pant`, `Fragt`, `Pakkegebyr`, `Kortgebyr`, `Gavekode rabat`, `Udbetalt opsparing...`, `Total`, `FAKTURA`, `Side X af Y`, addresses, `Fakturanr`, `Kundenr`, `Betalingsform`, `Forfaldsdato`, `Leveringsform`, `Leveringsdato`, and the column-header row).
  - `UNIT_RE = /\d+(?:[.,]\d+)?\s?(?:l|ml|cl|kg|g|stk\.?|pk\.?)\b/i`.
  - `RECIPE_RE = /^(.*?)\s+(\d+)\s+personer\b/i` with trailing price `0` / `0,00`.
  - `krNum(s)` parses `"8,50 kr."`/`"43,80"` → `8.5`/`43.8`.
  - Detection heuristic: if most non-ignored, non-category lines contain a unit token **and** trailing numbers on the *same* line → Format B; else Format A (vertical).

- [ ] **Step 5: Implement Format A parser** per §6.2 — walk lines; category header sets current category; otherwise read `name`, `unit`, integer `quantity` line, then collect consecutive `kr.` lines until a non-kr line; map the kr-lines (2 → [stk,total]; 3 → [stk,rabat,total]; last=total, first=stk).

- [ ] **Step 6: Implement Format B parser** per §6.3 — for each line: skip if ignored; if recipe → push recipe; else find unit via `UNIT_RE`, `name` = text before unit, parse trailing numbers (3 → [stk, qty, price]; 4 → [rabat, stk, qty, price]); `qty` = the integer (no comma) immediately before price.

- [ ] **Step 7: Recipe + unreadable handling** — recipe lines go to `recipes`; lines that match neither item nor ignore go to `unreadable`.

- [ ] **Step 8: Run tests, verify they pass** — `npx vitest run tests/nemlig` → PASS. Add `Mascarpone`/`Køl`-as-default category expectation only if derivable; otherwise category stays `''` for Format B (the preview lets the user set it, and the expected-result table in BILAG maps Mascarpone→Køl by name — implement a small name→category nicety only if cheap, else leave to user).

- [ ] **Step 9: Commit** — `git commit -am "Add nemlig order parser (Format A + B + recipes) with fixture tests"`

---

## Task 5: Data-access layer `src/lib/db.ts`

**Files:**
- Create: `src/lib/db.ts`

**Interfaces:**
- Produces (all take the `D1Database` as first arg so UI never touches D1 directly):
  - Weeks/meals: `getOrCreateWeek(db, year, week, startDate): Promise<Week>`; `getWeekWithMeals(db, weekId): Promise<{week, meals: Meal[]}>`; `listWeeks(db): Promise<Week[]>`; `upsertMeal(db, {weekId, weekday, title, isFlex, notes, cook, recipeUrl}): Promise<void>`; `createUpcomingWeek(db): Promise<Week>`.
  - Inventory: `listInventory(db, {location?, q?, category?}): Promise<Item[]>`; `addItem(db, item): Promise<void>`; `updateItem(db, id, patch): Promise<void>`; `consumeItem(db, id): Promise<void>` (qty-1, delete at 0); `deleteItem(db, id): Promise<void>`; `bulkInsert(db, items[]): Promise<number>`; `countByLocation(db): Promise<Record<Location,number>>`; `expiringSoon(db, days): Promise<Item[]>`.
- When a week is opened, lazily create its 7 `meals` rows (weekday 1..7) if missing.

- [ ] **Step 1:** Implement every function above with `db.prepare(...).bind(...).run()/.all()/.first()`. Keep types in this file (`Week`, `Meal`, `Item`) or import from a shared `types`. Use parameterized queries only. `expiringSoon` = `best_before IS NOT NULL AND best_before <= date('now', '+N days')`.
- [ ] **Step 2:** Manual smoke via a temporary script or the inventory page in Task 6.
- [ ] **Step 3: Commit** — `git commit -am "Add D1 data-access layer"`

---

## Task 6: Layout, nav, global styles, beholdning page (first real UI)

**Files:**
- Create: `src/components/Layout.astro`, `src/components/Nav.astro`, `src/components/ItemCard.astro`, `src/styles/global.css`, `src/pages/beholdning.astro`, `src/pages/api/inventory.ts`

**Interfaces:**
- Consumes: `db.ts` inventory functions, `locations.ts`.
- Produces: working inventory CRUD; reusable `Layout` (noindex, mobile viewport, nav) for all later pages.

- [ ] **Step 1:** `global.css` — design tokens (calm, max 2 accent colors, system/inherited font, generous spacing, card layout). Mobile-first; tables collapse to cards.
- [ ] **Step 2:** `Layout.astro` — `<html lang="da">`, `<meta name="robots" content="noindex">`, viewport meta, include `global.css`, slot, render `Nav`.
- [ ] **Step 3:** `Nav.astro` — links: Dashboard `/`, Madplan `/madplan`, Arkiv `/madplan/arkiv`, Beholdning `/beholdning`, Import `/import`; highlight active via `Astro.url.pathname`.
- [ ] **Step 4:** `beholdning.astro` — 4 sections (Køleskab/Fryser/Skab/Øvrigt) of `ItemCard`s; "Tilføj vare manuelt" form (navn, lokation, kategori, enhed, antal, bedst-før); search box + category filter (query params, server-rendered). Per-card actions: redigér, forbrug (−1), slet.
- [ ] **Step 5:** `api/inventory.ts` — POST handler dispatching on an `action` field (`add`|`update`|`consume`|`delete`) → calls `db.ts` → redirect back to `/beholdning`.
- [ ] **Step 6: Manual verify** in `npm run dev`: add, consume to zero (auto-delete), edit, delete, search, filter all work.
- [ ] **Step 7: Commit** — `git commit -am "Add layout, nav, styles and inventory page"`

---

## Task 7: Madplan + arkiv pages

**Files:**
- Create: `src/components/MealCard.astro`, `src/pages/madplan/index.astro`, `src/pages/madplan/arkiv.astro`, `src/pages/api/meals.ts`

**Interfaces:**
- Consumes: `db.ts` week/meal functions, `dates.ts`.
- Produces: editable current+upcoming weeks; read-only archive.

- [ ] **Step 1:** `MealCard.astro` — shows weekday name + title or "Fleks-aften 🍳" (visually distinct: accent border/background + icon) or empty "Tilføj ret"; props include `readOnly`.
- [ ] **Step 2:** `madplan/index.astro` — ensure current week exists (`getOrCreateWeek` for today's ISO week) + create its 7 meal rows; render current week, then any upcoming weeks; "Opret kommende uge" button. Each day editable via small inline form/dialog (title, flex-toggle, note, cook, recipe_url).
- [ ] **Step 3:** `api/meals.ts` — POST: `upsertMeal` / toggle flex / `createUpcomingWeek` based on `action`; redirect back.
- [ ] **Step 4:** `madplan/arkiv.astro` — `listWeeks` filtered to `weekStatus==='historisk'`, newest→oldest, rendered with `MealCard readOnly`.
- [ ] **Step 5: Manual verify:** edit a day, mark flex (shows distinct), create upcoming week, confirm a past week shows under arkiv.
- [ ] **Step 6: Commit** — `git commit -am "Add meal plan and archive pages"`

---

## Task 8: Import page (paste/upload → preview → confirm)

**Files:**
- Create: `src/pages/import.astro`, `src/pages/api/import.ts`
- Modify: `package.json` (add `pdfjs-dist` only if doing PDF upload now)

**Interfaces:**
- Consumes: `parseNemlig`, `defaultLocationForCategory`, `db.bulkInsert`, `db.upsertMeal`.
- Produces: human-confirmed import into inventory; recipe→meal suggestion.

- [ ] **Step 1:** `import.astro` step 1 — textarea to paste raw text; (optional) file input for PDF. "Parse" runs `parseNemlig` (server POST or client island) and renders the **mandatory confirmation table** (§6.7): per row `[✓ Inkludér] · Varenavn · Kategori · Enhed · Antal · Lokation (dropdown, prefilled from mapping) · Bedst før (optional)`. Show recipe lines with "Indsæt som forslag i madplanen?" (day picker) and an "kunne ikke læses" section for `unreadable`.
- [ ] **Step 2:** Optional "Slå sammen med eksisterende vare i samme lokation" checkbox per row.
- [ ] **Step 3:** "Tilføj N varer til beholdning" → POST to `api/import.ts` with the edited rows → `bulkInsert` (`source='nemlig'`, `added_at=today`), merging where requested. Recipe insert → `upsertMeal` on chosen day.
- [ ] **Step 4:** Show receipt: "Tilføjede N varer (heraf P i Øvrigt) · sprang M opskrift-linjer over".
- [ ] **Step 5:** `api/import.ts` — validate, insert, return receipt. **Nothing is inserted without this confirmation POST.**
- [ ] **Step 6: Manual verify** with both BILAG fixtures: correct split, default locations correct, recipe offered, totals ignored.
- [ ] **Step 7: Commit** — `git commit -am "Add nemlig import page with mandatory confirmation"`

---

## Task 9: Dashboard

**Files:**
- Modify/Create: `src/pages/index.astro`

**Interfaces:**
- Consumes: `db.getOrCreateWeek`+`getWeekWithMeals`, `db.countByLocation`, `db.expiringSoon`, `dates.ts`.

- [ ] **Step 1:** Render this week's 7 day-cards (reuse `MealCard`, read-only-ish with quick link to `/madplan`) + inventory overview (count per location + "udløber snart" count from `expiringSoon(3)`), mobile-correct.
- [ ] **Step 2: Manual verify** on a narrow viewport.
- [ ] **Step 3: Commit** — `git commit -am "Add dashboard"`

---

## Task 10: Deploy — repo, Pages, secret, remote migration

**Files:** none (ops). Resolve the open decisions first (see "Open decisions" below).

- [ ] **Step 1:** Create remote git repo. If `gh` is installed: `gh repo create nova-madplan --private --source=. --push`. Else create the repo on github.com manually and `git remote add origin … && git push -u origin main`, **or** skip GitHub and deploy directly with Wrangler.
- [ ] **Step 2:** First deploy: `wrangler pages deploy ./dist --project-name madplan` (after `npm run build`), or connect the repo in the Cloudflare dashboard for Git-integration builds.
- [ ] **Step 3:** Apply migration to **REMOTE** D1: `wrangler d1 migrations apply madplan --remote` (classic pitfall — must target remote, not just local).
- [ ] **Step 4:** Set the production secret: `wrangler pages secret put SITE_PASSWORD --project-name madplan` → enter `mikey`.
- [ ] **Step 5:** Bind D1 to the Pages project (dashboard → Settings → Functions → D1 bindings: `DB` → `madplan`), if not inherited from `wrangler.toml`.
- [ ] **Step 6:** Add custom domain `madplan.nova-tech.dk` on the Pages project (one DNS record; DNS already on Cloudflare). **Requires the deploy to be on the Cloudflare account that holds `nova-tech.dk`** — verify the logged-in account matches before this step.
- [ ] **Step 7:** Smoke test the live URL: login gate works, can add inventory, can import a pasted order, meal plan edits persist.

---

## Open decisions (resolve before Task 10; do not block Tasks 0–9)

1. **GitHub repo:** `gh` is not installed locally. Options: (a) install `gh` (`winget install GitHub.cli`), (b) create the repo manually on github.com + push over HTTPS/SSH, (c) skip GitHub entirely and deploy via `wrangler pages deploy`. The spec asks for a GitHub repo; (a) or (b) satisfies it.
2. **Cloudflare account:** Wrangler is logged in as `mikey_andersen93@hotmail.dk` (account `bce1ccddbd3b2947680fb466a5c590ef`). The custom domain step requires this to be the account that holds `nova-tech.dk` DNS. Confirm, or `wrangler login` to the correct account before deploy.

---

## Self-review notes

- **Spec coverage:** §1 stack→Task 0; §3 routes→Tasks 6–9; §4 schema→Task 1; §5 meal logic→Task 7; §6 nemlig→Tasks 4+8; §7 inventory→Task 6; §8 auth→Task 2; §9 deploy→Tasks 1+10; §10 DoD→Tasks 6–10; aesthetics §2→Task 6 styles. All covered.
- **Auth note:** spec §8 says "ét delt password" gate (not Cloudflare Access) — implemented as middleware cookie gate; the §10 line mentioning "Cloudflare Access" is superseded by the detailed §8 single-password decision.
- **Design inheritance (§2):** inherit nova-tech.dk tokens if available; the existing sibling repo `nova-erdetfredagloerdag` may hold reusable tokens — check during Task 6, otherwise use the minimal calm fallback.
- **Type consistency:** `Location` slugs, `parseNemlig`/`ParseResult`, and `db.ts` signatures are referenced consistently across tasks.
