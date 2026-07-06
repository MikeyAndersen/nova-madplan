# Fri-tekst-quickfill af ugeplan — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Genindføre fri-tekst-udfyldning af en uge ("Dag: mad"-linjer) med en preview-skærm og en "+AI forslag"-genvej — kun frontend, ingen backend-ændring.

**Architecture:** Astro SSR + BFF-mønster: browseren fetcher to nye session-gated JSON-ruter (`/api/weekplan/preview`, `/api/weekplan/apply`) der server-side vedhæfter `LIFEHUB_API_TOKEN` og proxyer mod FastAPI. Al parsing/matching er rene, testede funktioner. Preview → bekræft → looper eksisterende `PUT /api/weekplan/day`. "+AI forslag" genbruger eksisterende `/forslag` + `refresh`/`poll`.

**Tech Stack:** Astro 6 (`output: server`, `@astrojs/cloudflare`), TypeScript, vitest. Ingen nye dependencies.

## Global Constraints

- Sprog: dokumentation/UI dansk, kode/typer/JSON engelsk.
- BFF-mønster: `LIFEHUB_API_TOKEN` når ALDRIG klienten. Kun `src/lib/api.ts::getApi()` taler med backenden; nye ruter kalder gennem den.
- Ingen backend-ændring; ingen nye backend-endpoints. Kun eksisterende: `getWeekplan/getCurrentWeekplan`, `listDishes`, `createDish`, `putDay`, `refreshSuggestions`.
- Filstil: filer under `src/lib/` bruger 2-mellemrums-indryk (jf. `dates.ts`); ruter under `src/pages/api/` bruger tabs (jf. `api/day.ts`). Match nabofilen.
- Ugeplanens `days` er altid 7, ordnet mandag→søndag; ugedag `n` (1–7) = `week.days[n-1]`.
- `PUT /api/weekplan/day` body: `{date, status, dish_id, note}`; `Day.status ∈ {planned|cooked|skipped|empty}`.
- Fejl må aldrig give hvid side: GET-fejl → banner; mutationer → best-effort pr. dag + rapport.

---

## Filstruktur

| Fil | Ansvar | Status |
|---|---|---|
| `src/lib/weekplan.ts` | Ren parser `parseWeekPlan(raw): WeekPlanEntry[]` | Gendannes fra `47b8297` |
| `tests/weekplan.test.ts` | Parser-tests | Gendannes fra `47b8297` |
| `src/lib/weekplan-match.ts` | `normalizeTitle`, `matchDish` (ren) | Ny |
| `tests/weekplan-match.test.ts` | Match-tests | Ny |
| `src/lib/weekplan-preview.ts` | `PreviewDay`/`ApplyDecision`-typer + `buildPreview` (ren) | Ny |
| `tests/weekplan-preview.test.ts` | Preview-tests | Ny |
| `src/pages/api/weekplan/preview.ts` | BFF: parse+match+preview → JSON | Ny |
| `src/pages/api/weekplan/apply.ts` | BFF: anvend beslutninger (best-effort) → JSON | Ny |
| `src/components/QuickfillPanel.astro` | Paste-felt, preview-UI, bekræft, +AI forslag | Ny |
| `src/pages/madplan/index.astro` | Indlejr `QuickfillPanel` | Modificeres |

---

### Task 1: Gendan parser + tests fra git

**Files:**
- Create: `src/lib/weekplan.ts` (fra `47b8297`)
- Test: `tests/weekplan.test.ts` (fra `47b8297`)

**Interfaces:**
- Produces: `parseWeekPlan(raw: string): WeekPlanEntry[]` og `interface WeekPlanEntry { weekday: number; title: string }` (weekday 1=man … 7=søn).

- [ ] **Step 1: Gendan begge filer fra git-historikken**

Run:
```bash
git show 47b8297:src/lib/weekplan.ts > src/lib/weekplan.ts
git show 47b8297:tests/weekplan.test.ts > tests/weekplan.test.ts
```

- [ ] **Step 2: Kør parser-testene — de skal passere som-de-er**

Run: `npx vitest run tests/weekplan.test.ts`
Expected: PASS (6 tests: dag-format, forkortelser, blanke linjer, ikke-dag-token, rækkefølge-fallback, sidste-linje-vinder)

- [ ] **Step 3: Commit**

```bash
git add src/lib/weekplan.ts tests/weekplan.test.ts
git commit -m "feat: gendan fri-tekst weekplan-parser fra git"
```

---

### Task 2: Ret-matchning (`weekplan-match.ts`)

**Files:**
- Create: `src/lib/weekplan-match.ts`
- Test: `tests/weekplan-match.test.ts`

**Interfaces:**
- Consumes: `Dish` fra `./api.types`.
- Produces: `normalizeTitle(s: string): string`; `matchDish(title: string, dishes: Dish[]): number | null`.

- [ ] **Step 1: Skriv de fejlende tests**

```ts
// tests/weekplan-match.test.ts
import { describe, it, expect } from 'vitest';
import { normalizeTitle, matchDish } from '../src/lib/weekplan-match';
import type { Dish } from '../src/lib/api.types';

const dish = (id: number, name: string): Dish => ({
  id, name, tags: [], recurring_weekly: false, ingredients: [], last_made: null, active: true,
});

describe('normalizeTitle', () => {
  it('folder case, whitespace og ø/å/æ', () => {
    expect(normalizeTitle('  Kødsovs  ')).toBe('kodsovs');
    expect(normalizeTitle('Rød GRØD')).toBe('rod grod');
    expect(normalizeTitle('Æblekage')).toBe('aeblekage');
  });
});

describe('matchDish', () => {
  const dishes = [dish(3, 'Kødsovs'), dish(7, 'Grøn salat')];
  it('matcher uanset case og æøå', () => {
    expect(matchDish('kodsovs', dishes)).toBe(3);
    expect(matchDish('  KØDSOVS ', dishes)).toBe(3);
  });
  it('returnerer null uden match', () => {
    expect(matchDish('Tacos', dishes)).toBeNull();
  });
  it('returnerer null for tom titel', () => {
    expect(matchDish('   ', dishes)).toBeNull();
  });
});
```

- [ ] **Step 2: Kør testene — skal fejle (modul findes ikke)**

Run: `npx vitest run tests/weekplan-match.test.ts`
Expected: FAIL — "Cannot find module '../src/lib/weekplan-match'"

- [ ] **Step 3: Implementér**

```ts
// src/lib/weekplan-match.ts
import type { Dish } from './api.types';

/** Normalisér til sammenligning: trim, lowercase, fold ø/å/æ, kollaps whitespace. */
export function normalizeTitle(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/ø/g, 'o')
    .replace(/å/g, 'a')
    .replace(/æ/g, 'ae')
    .replace(/\s+/g, ' ');
}

/** Id på en ret hvis navnet matcher titlen (normaliseret), ellers null. */
export function matchDish(title: string, dishes: Dish[]): number | null {
  const key = normalizeTitle(title);
  if (!key) return null;
  const hit = dishes.find((d) => normalizeTitle(d.name) === key);
  return hit ? hit.id : null;
}
```

- [ ] **Step 4: Kør testene — skal passere**

Run: `npx vitest run tests/weekplan-match.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/weekplan-match.ts tests/weekplan-match.test.ts
git commit -m "feat: ret-matchning for fri-tekst-quickfill"
```

---

### Task 3: Preview-sammensætning (`weekplan-preview.ts`)

**Files:**
- Create: `src/lib/weekplan-preview.ts`
- Test: `tests/weekplan-preview.test.ts`

**Interfaces:**
- Consumes: `WeekPlan, Dish` fra `./api.types`; `WeekPlanEntry` fra `./weekplan`; `matchDish` fra `./weekplan-match`.
- Produces:
  - `type PreviewKind = 'match' | 'new' | 'conflict' | 'cooked' | 'keep' | 'empty'`
  - `interface PreviewDay { date: string; weekday: number; parsedTitle?: string; kind: PreviewKind; matchedDishId?: number; matchedDishName?: string; currentDishName?: string }`
  - `interface ApplyDecision { date: string; action: 'create_dish' | 'use_dish' | 'note' | 'skip'; dishId?: number; title?: string }`
  - `interface ApplyResult { date: string; ok: boolean; error?: string }`
  - `buildPreview(parsed: WeekPlanEntry[], week: WeekPlan, dishes: Dish[]): PreviewDay[]`

> **Note:** `'keep'` (planned dag der ikke nævnes i pastet → beholdes urørt) er en bevidst udvidelse ud over spec'ens 5 kinds, så preview'et kan skelne "allerede planlagt, ikke i tekst" fra "tom". "+AI forslag" rører alligevel aldrig planned/cooked (accept-uge springer dem over).

- [ ] **Step 1: Skriv de fejlende tests**

```ts
// tests/weekplan-preview.test.ts
import { describe, it, expect } from 'vitest';
import { buildPreview } from '../src/lib/weekplan-preview';
import type { WeekPlan, Day, Dish } from '../src/lib/api.types';

const dish = (id: number, name: string): Dish => ({
  id, name, tags: [], recurring_weekly: false, ingredients: [], last_made: null, active: true,
});
const day = (date: string, weekday: string, over: Partial<Day> = {}): Day => ({
  date, weekday, dish_id: null, dish_name: null, status: 'empty', note: null, ...over,
});
// Uge med mandag=2026-07-06 … søndag=2026-07-12
const week = (days: Day[]): WeekPlan => ({ week_start: '2026-07-06', days, updated_at: '' });
const DATES = ['2026-07-06','2026-07-07','2026-07-08','2026-07-09','2026-07-10','2026-07-11','2026-07-12'];
const WD = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
const emptyWeek = () => week(DATES.map((d, i) => day(d, WD[i])));

const dishes = [dish(3, 'Kødsovs')];

describe('buildPreview', () => {
  it('match: kendt ret på en tom dag', () => {
    const p = buildPreview([{ weekday: 1, title: 'kødsovs' }], emptyWeek(), dishes);
    expect(p[0]).toMatchObject({ date: '2026-07-06', weekday: 1, kind: 'match', matchedDishId: 3 });
  });

  it('new: ukendt titel på en tom dag', () => {
    const p = buildPreview([{ weekday: 2, title: 'Tacos' }], emptyWeek(), dishes);
    expect(p[1]).toMatchObject({ weekday: 2, kind: 'new', parsedTitle: 'Tacos' });
  });

  it('conflict: paste rammer en allerede planlagt dag', () => {
    const w = emptyWeek();
    w.days[2] = day(DATES[2], WD[2], { status: 'planned', dish_id: 9, dish_name: 'Pizza' });
    const p = buildPreview([{ weekday: 3, title: 'Kødsovs' }], w, dishes);
    expect(p[2]).toMatchObject({ weekday: 3, kind: 'conflict', currentDishName: 'Pizza', matchedDishId: 3 });
  });

  it('cooked: låst uanset paste', () => {
    const w = emptyWeek();
    w.days[3] = day(DATES[3], WD[3], { status: 'cooked', dish_id: 5, dish_name: 'Suppe' });
    const p = buildPreview([{ weekday: 4, title: 'Kødsovs' }], w, dishes);
    expect(p[3]).toMatchObject({ weekday: 4, kind: 'cooked', currentDishName: 'Suppe' });
  });

  it('keep: planlagt dag uden paste-linje', () => {
    const w = emptyWeek();
    w.days[4] = day(DATES[4], WD[4], { status: 'planned', dish_id: 9, dish_name: 'Pizza' });
    const p = buildPreview([], w, dishes);
    expect(p[4]).toMatchObject({ weekday: 5, kind: 'keep', currentDishName: 'Pizza' });
  });

  it('empty: tom dag uden paste-linje', () => {
    const p = buildPreview([], emptyWeek(), dishes);
    expect(p[6]).toMatchObject({ weekday: 7, kind: 'empty' });
  });
});
```

- [ ] **Step 2: Kør testene — skal fejle**

Run: `npx vitest run tests/weekplan-preview.test.ts`
Expected: FAIL — "Cannot find module '../src/lib/weekplan-preview'"

- [ ] **Step 3: Implementér**

```ts
// src/lib/weekplan-preview.ts
import type { WeekPlan, Dish } from './api.types';
import type { WeekPlanEntry } from './weekplan';
import { matchDish } from './weekplan-match';

export type PreviewKind = 'match' | 'new' | 'conflict' | 'cooked' | 'keep' | 'empty';

export interface PreviewDay {
  date: string;
  weekday: number; // 1=man … 7=søn
  parsedTitle?: string;
  kind: PreviewKind;
  matchedDishId?: number;
  matchedDishName?: string;
  currentDishName?: string;
}

export interface ApplyDecision {
  date: string;
  action: 'create_dish' | 'use_dish' | 'note' | 'skip';
  dishId?: number;
  title?: string;
}

export interface ApplyResult {
  date: string;
  ok: boolean;
  error?: string;
}

/** Sammensæt preview pr. dag ud fra parsede linjer + ugens nuværende tilstand. */
export function buildPreview(parsed: WeekPlanEntry[], week: WeekPlan, dishes: Dish[]): PreviewDay[] {
  const byDay = new Map<number, string>(parsed.map((e) => [e.weekday, e.title]));
  return week.days.map((day, i) => {
    const weekday = i + 1;
    const currentDishName = day.dish_name ?? undefined;
    const title = byDay.get(weekday);

    if (day.status === 'cooked') {
      return { date: day.date, weekday, kind: 'cooked', currentDishName };
    }
    if (title == null) {
      const kind: PreviewKind = day.status === 'planned' ? 'keep' : 'empty';
      return { date: day.date, weekday, kind, currentDishName };
    }
    const matchId = matchDish(title, dishes);
    const matched = matchId != null ? dishes.find((d) => d.id === matchId) : undefined;
    if (day.status === 'planned') {
      return {
        date: day.date, weekday, parsedTitle: title, kind: 'conflict',
        currentDishName,
        matchedDishId: matchId ?? undefined, matchedDishName: matched?.name,
      };
    }
    if (matchId != null) {
      return {
        date: day.date, weekday, parsedTitle: title, kind: 'match',
        matchedDishId: matchId, matchedDishName: matched?.name,
      };
    }
    return { date: day.date, weekday, parsedTitle: title, kind: 'new' };
  });
}
```

- [ ] **Step 4: Kør testene — skal passere**

Run: `npx vitest run tests/weekplan-preview.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/weekplan-preview.ts tests/weekplan-preview.test.ts
git commit -m "feat: preview-sammensætning for fri-tekst-quickfill"
```

---

### Task 4: BFF preview-rute

**Files:**
- Create: `src/pages/api/weekplan/preview.ts`

**Interfaces:**
- Consumes: `getApi` fra `../../../lib/api`; `parseWeekPlan`, `buildPreview`.
- Produces: `POST /api/weekplan/preview` — body `{weekStart?: string, raw?: string}` → `{week_start: string, days: PreviewDay[]}` (200) eller `{error}` (502).

- [ ] **Step 1: Skriv ruten** (tabs, mirror `api/day.ts`)

```ts
// src/pages/api/weekplan/preview.ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
import { parseWeekPlan } from '../../../lib/weekplan';
import { buildPreview } from '../../../lib/weekplan-preview';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const body = (await request.json().catch(() => ({}))) as { weekStart?: string; raw?: string };
	try {
		const week = body.weekStart ? await api.getWeekplan(body.weekStart) : await api.getCurrentWeekplan();
		const dishes = await api.listDishes(false);
		const days = buildPreview(parseWeekPlan(body.raw ?? ''), week, dishes);
		return Response.json({ week_start: week.week_start, days });
	} catch {
		return Response.json({ error: 'preview_failed' }, { status: 502 });
	}
};
```

- [ ] **Step 2: Verificér at det bygger (type/compile)**

Run: `npm run build`
Expected: "Server built" uden TypeScript-fejl; `dist/` opdateret.

- [ ] **Step 3: Commit**

```bash
git add src/pages/api/weekplan/preview.ts
git commit -m "feat: BFF preview-rute for fri-tekst-quickfill"
```

---

### Task 5: BFF apply-rute

**Files:**
- Create: `src/pages/api/weekplan/apply.ts`

**Interfaces:**
- Consumes: `getApi`; `ApplyDecision`, `ApplyResult` fra `../../../lib/weekplan-preview`.
- Produces: `POST /api/weekplan/apply` — body `{decisions: ApplyDecision[]}` → `{results: ApplyResult[]}` (200). Best-effort pr. dag; opretter nye retter via `createDish`, sætter dage via `putDay(status:'planned')`.

- [ ] **Step 1: Skriv ruten** (tabs)

```ts
// src/pages/api/weekplan/apply.ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
import type { ApplyDecision, ApplyResult } from '../../../lib/weekplan-preview';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const body = (await request.json().catch(() => ({}))) as { decisions?: ApplyDecision[] };
	const results: ApplyResult[] = [];
	for (const d of body.decisions ?? []) {
		if (d.action === 'skip') {
			results.push({ date: d.date, ok: true });
			continue;
		}
		try {
			let dishId: number | null = null;
			let note: string | null = null;
			if (d.action === 'use_dish') dishId = d.dishId ?? null;
			else if (d.action === 'create_dish') dishId = (await api.createDish({ name: (d.title ?? '').trim() })).id;
			else if (d.action === 'note') note = (d.title ?? '').trim() || null;
			await api.putDay({ date: d.date, status: 'planned', dish_id: dishId, note });
			results.push({ date: d.date, ok: true });
		} catch (e) {
			results.push({ date: d.date, ok: false, error: e instanceof Error ? e.message : 'fejl' });
		}
	}
	return Response.json({ results });
};
```

- [ ] **Step 2: Verificér at det bygger**

Run: `npm run build`
Expected: "Server built" uden TypeScript-fejl.

- [ ] **Step 3: Commit**

```bash
git add src/pages/api/weekplan/apply.ts
git commit -m "feat: BFF apply-rute for fri-tekst-quickfill"
```

---

### Task 6: `QuickfillPanel.astro` (paste + preview + bekræft + +AI forslag)

**Files:**
- Create: `src/components/QuickfillPanel.astro`

**Interfaces:**
- Consumes (props): `weekStart: string`, `dishes: Dish[]`.
- Kalder BFF `/api/weekplan/preview` og `/api/weekplan/apply`; ved "+AI forslag" `POST /api/suggestions/refresh` + `GET /api/suggestions/poll` (mirror af `forslag.astro`-scriptet) → naviger til `/forslag`.
- Bygger `ApplyDecision[]` klient-side ud fra `PreviewDay.kind` + brugervalg.

> Beslutnings-mapping pr. kind: `match` → `use_dish(matchedDishId)`; `new` → radiovalg *opret*→`create_dish(title)` / *note*→`note(title)` / *vælg eksisterende*→ (matcher datalist → `use_dish(id)`, ellers `create_dish(indtastet)`); `conflict` → checkbox *overskriv*: til → (matchedDishId ? `use_dish` : `create_dish(parsedTitle)`), fra → `skip`; `cooked`/`keep`/`empty` → `skip`.

- [ ] **Step 1: Skriv komponenten** (2-mellemrum; markup + is:inline-script)

```astro
---
import type { Dish } from '../lib/api.types';
interface Props { weekStart: string; dishes: Dish[]; }
const { weekStart, dishes } = Astro.props;
---
<details class="quickfill">
  <summary>Indsæt uge fra tekst</summary>
  <textarea id="qf-raw" rows="7" placeholder="Mandag: Kødsovs&#10;Tirsdag: grill+rester&#10;…"></textarea>
  <div class="row" style="gap:0.5rem; margin:0.5rem 0;">
    <button id="qf-preview" class="btn-primary" type="button">Vis preview</button>
    <span id="qf-status" class="small muted"></span>
  </div>
  <div id="qf-preview-list"></div>
  <div class="row" id="qf-actions" style="gap:0.5rem; display:none; margin-top:0.6rem;">
    <button id="qf-apply" class="btn-primary" type="button">Bekræft og gem</button>
    <button id="qf-ai" class="btn-sm" type="button">+AI forslag for resten</button>
    <span id="qf-ai-status" class="small muted"></span>
  </div>
  <datalist id="qf-dishes">
    {dishes.map((d) => <option value={d.name} data-id={d.id}></option>)}
  </datalist>
</details>

<script is:inline define:vars={{ weekStart }}>
  (function () {
    var raw = document.getElementById('qf-raw');
    var status = document.getElementById('qf-status');
    var list = document.getElementById('qf-preview-list');
    var actions = document.getElementById('qf-actions');
    var dl = document.getElementById('qf-dishes');
    var current = [];

    function idForName(name) {
      var o = Array.prototype.find.call(dl.options, function (x) { return x.value === name; });
      return o ? Number(o.getAttribute('data-id')) : null;
    }

    function rowHtml(p) {
      var head = '<strong>' + p.date + '</strong> ';
      if (p.kind === 'match') return head + '→ ' + p.matchedDishName + ' <span class="tag">match</span>';
      if (p.kind === 'cooked') return head + '🔒 ' + (p.currentDishName || 'tilberedt') + ' <span class="tag">låst</span>';
      if (p.kind === 'keep') return head + (p.currentDishName || '') + ' <span class="tag">beholdes</span>';
      if (p.kind === 'empty') return head + '<span class="muted">tom — fyldes evt. af +AI</span>';
      if (p.kind === 'new') {
        var n = 'nk-' + p.weekday;
        return head + '“' + p.parsedTitle + '” <span class="tag">ny</span><div class="small" style="margin-top:.3rem">'
          + '<label><input type="radio" name="' + n + '" value="create" checked> Opret som ret</label> '
          + '<label><input type="radio" name="' + n + '" value="note"> Note</label> '
          + '<label><input type="radio" name="' + n + '" value="existing"> Vælg: '
          + '<input class="dish-input" list="qf-dishes" data-existing placeholder="ret…"></label></div>';
      }
      // conflict
      return head + 'nu: ' + (p.currentDishName || '?') + ' → “' + p.parsedTitle + '” <span class="tag">konflikt</span> '
        + '<label class="small"><input type="checkbox" data-overwrite> overskriv</label>';
    }

    function decisionFor(el, p) {
      if (p.kind === 'match') return { date: p.date, action: 'use_dish', dishId: p.matchedDishId };
      if (p.kind === 'cooked' || p.kind === 'keep' || p.kind === 'empty') return { date: p.date, action: 'skip' };
      if (p.kind === 'new') {
        var sel = el.querySelector('input[type=radio]:checked');
        var mode = sel ? sel.value : 'create';
        if (mode === 'note') return { date: p.date, action: 'note', title: p.parsedTitle };
        if (mode === 'existing') {
          var typed = (el.querySelector('[data-existing]').value || '').trim();
          var id = idForName(typed);
          return id ? { date: p.date, action: 'use_dish', dishId: id }
                    : { date: p.date, action: 'create_dish', title: typed || p.parsedTitle };
        }
        return { date: p.date, action: 'create_dish', title: p.parsedTitle };
      }
      // conflict
      var ow = el.querySelector('[data-overwrite]');
      if (!ow || !ow.checked) return { date: p.date, action: 'skip' };
      return p.matchedDishId ? { date: p.date, action: 'use_dish', dishId: p.matchedDishId }
                             : { date: p.date, action: 'create_dish', title: p.parsedTitle };
    }

    document.getElementById('qf-preview').addEventListener('click', async function () {
      status.textContent = 'Henter preview…';
      list.innerHTML = '';
      try {
        var r = await fetch('/api/weekplan/preview', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ weekStart: weekStart, raw: raw.value }),
        });
        var j = await r.json();
        if (!r.ok || !j.days) throw new Error('preview');
        current = j.days;
        current.forEach(function (p) {
          var div = document.createElement('div');
          div.className = 'card';
          div.dataset.weekday = p.weekday;
          div.innerHTML = rowHtml(p);
          list.appendChild(div);
        });
        actions.style.display = 'flex';
        status.textContent = '';
      } catch (e) {
        status.textContent = 'Kunne ikke hente preview.';
      }
    });

    document.getElementById('qf-apply').addEventListener('click', async function () {
      status.textContent = 'Gemmer…';
      var rows = list.querySelectorAll('.card');
      var decisions = current.map(function (p, i) { return decisionFor(rows[i], p); });
      try {
        var r = await fetch('/api/weekplan/apply', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ decisions: decisions }),
        });
        var j = await r.json();
        var failed = (j.results || []).filter(function (x) { return !x.ok; });
        if (failed.length) { status.textContent = 'Nogle dage fejlede: ' + failed.map(function (x){return x.date;}).join(', '); return; }
        location.href = '/madplan?start=' + encodeURIComponent(weekStart);
      } catch (e) {
        status.textContent = 'Kunne ikke gemme.';
      }
    });

    document.getElementById('qf-ai').addEventListener('click', async function () {
      var aiStatus = document.getElementById('qf-ai-status');
      aiStatus.textContent = 'Arbejder… (7b på CPU kan tage 1–2 min)';
      try {
        var before = '';
        var pr = await fetch('/api/suggestions/poll'); var pj = await pr.json(); before = pj.updated_at || '';
        await fetch('/api/suggestions/refresh', { method: 'POST' });
        var started = Date.now();
        var timer = setInterval(async function () {
          if (Date.now() - started > 180000) { clearInterval(timer); aiStatus.textContent = 'Tog for lang tid — åbn Forslag manuelt.'; return; }
          var r = await fetch('/api/suggestions/poll'); var j = await r.json();
          if (j.updated_at && j.updated_at !== before) { clearInterval(timer); location.href = '/forslag'; }
        }, 5000);
      } catch (e) {
        aiStatus.textContent = 'Kunne ikke starte. Åbn Forslag manuelt.';
      }
    });
  })();
</script>

<style>
  .quickfill { margin: 0 0 1rem; }
  .quickfill summary { cursor: pointer; font-weight: 600; }
  .quickfill textarea { width: 100%; margin-top: 0.6rem; font: inherit; padding: 0.6rem; }
  .quickfill .card label { margin-right: 0.6rem; }
</style>
```

- [ ] **Step 2: Verificér at det bygger**

Run: `npm run build`
Expected: "Server built" uden fejl.

- [ ] **Step 3: Commit**

```bash
git add src/components/QuickfillPanel.astro
git commit -m "feat: QuickfillPanel — paste, preview, bekræft, +AI forslag"
```

---

### Task 7: Indlejr panelet i `/madplan`

**Files:**
- Modify: `src/pages/madplan/index.astro`

**Interfaces:**
- Consumes: `QuickfillPanel` med `weekStart={ws}` og `dishes={dishes}` (begge findes allerede i frontmatter).

- [ ] **Step 1: Importér komponenten** — tilføj efter linje 3 (`import MealCard …`)

```astro
import QuickfillPanel from '../../components/QuickfillPanel.astro';
```

- [ ] **Step 2: Render panelet** — indsæt lige efter `</div>` for `section-head` (efter linje 34), før `{plan && (`

```astro
  {plan && <QuickfillPanel weekStart={ws} dishes={dishes} />}
```

- [ ] **Step 3: Verificér build + hele testsuiten**

Run: `npm run build && npm test`
Expected: build "Server built"; alle tests PASS (parser 6 + match 3 + preview 6 + eksisterende dates/api/accept-week).

- [ ] **Step 4: Commit**

```bash
git add src/pages/madplan/index.astro
git commit -m "feat: vis QuickfillPanel på madplan-siden"
```

---

### Task 8: Manuel røgtest mod live + afslut

**Files:** ingen (verifikation).

- [ ] **Step 1: Deploy til preview/prod og røgtest**

Deploy: `npx wrangler deploy` (eller test lokalt via `.claude/skills/verify` mod lokal backend).
Manuelt på `madplan.nova-tech.dk/madplan`:
1. Åbn "Indsæt uge fra tekst", skriv `Mandag: Kødsovs` + `Tirsdag: grill+rester` → **Vis preview**.
2. Bekræft at Kødsovs vises som *match* (hvis retten findes) og grill+rester som *ny* med opret/note/vælg.
3. Vælg *note* for grill+rester, **Bekræft og gem** → siden genindlæses, mandag+tirsdag er planned.
4. Tryk **+AI forslag for resten** → efter genberegning lander du på `/forslag` med forslag til de tomme dage.

- [ ] **Step 2: Verificér accept-kriterier fra spec'en**

- Preview viser match/ny/konflikt/cooked/tom korrekt.
- Cooked-dage røres aldrig.
- Backend nede midt i apply → best-effort-rapport, ingen hvid side.
- `LIFEHUB_API_TOKEN` ikke i klient-bundle (DevTools-søgning).

---

## Self-Review (udført)

- **Spec-dækning:** §1 flow → Tasks 6–8; §2 komponenter → Tasks 1–7 (parser, match, preview, 2 BFF-ruter, UI); §3 fejl/edge → apply best-effort (Task 5) + Task 8; §4 test → Tasks 1–3 (+ suite i Task 7). "+AI forslag" (§0.2) → Task 6 AI-knap. Ingen udækkede krav.
- **Placeholder-scan:** ingen TBD/TODO; al kode er komplet.
- **Type-konsistens:** `WeekPlanEntry` (Task 1) bruges i `buildPreview` (Task 3) og preview-ruten (Task 4); `PreviewDay`/`ApplyDecision`/`ApplyResult` (Task 3) bruges i ruter (4,5) og UI (6); `matchDish` (Task 2) i `buildPreview` (Task 3). Navne stemmer på tværs.
