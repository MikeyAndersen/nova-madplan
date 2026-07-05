# Fase 7 — Madplan-frontend-port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the old Astro/D1 madplan frontend to talk to the new FastAPI backend via a server-side BFF, reusing the original design wholesale, with weekplan / forslag / retter screens and shared-password login.

**Architecture:** Astro SSR on Cloudflare (@astrojs/cloudflare adapter) at the repo root, coexisting with `api/` (the FastAPI backend). Browser talks only to same-origin Astro SSR pages + BFF API routes; the BFF attaches `Authorization: Bearer <LIFEHUB_API_TOKEN>` server-side and calls `MADPLAN_API_BASE`. Datalayer is a single typed REST client (`src/lib/api.ts`) replacing the old D1 `db.ts`.

**Tech Stack:** Astro 6, @astrojs/cloudflare 13, TypeScript, Vitest, Cloudflare Pages/Workers, Wrangler.

## Global Constraints

- Documentation Danish; code/API/JSON keys English. (spec §0)
- No changes to `nova-madplan/api` in Spec A. Missing endpoint → stop and report. (spec §0)
- No secrets in code or client bundle — only Pages env vars: `MADPLAN_API_BASE`, `LIFEHUB_API_TOKEN`, `SITE_PASSWORD`. Token must NEVER reach the browser/client bundle. (spec §0.2, §3.5.5)
- D1 bindings, wrangler D1 config, and all lager/pris code removed entirely (dead code out, not commented). `grep -ri d1 src wrangler.jsonc` must be empty. (spec §3.5.7)
- Commit/push only when the user asks — but this plan uses local commits per task; do NOT push. (project guardrail)
- Reuse the original design from commit `c081267` wherever possible (spec §2). Restore reused files verbatim via `git show c081267:<path>`; only adapt what the datalayer change forces.
- Login model unchanged: shared password `SITE_PASSWORD` + HMAC session cookie. All routes except `/login`,`/logout` require a session. (spec §0.3, §3.2)
- Backend contracts are verified in `api/app/`: `Day{date,weekday,dish_id,dish_name,status(planned|cooked|skipped|empty),note}`; `PUT /api/weekplan/day` body `{date,status,dish_id,note}` returns `WeekPlan`; dish update is `PUT /api/dishes/{id}` (not PATCH); `DELETE /api/dishes/{id}` is soft delete (204); `POST /api/suggestions/refresh` returns 202; `POST /api/suggestions/accept` body `{date,dish_id}` returns `WeekPlan`.

---

## File Structure

Frontend restored at repo root (matches the Cloudflare Pages/Worker project that already deploys `madplan.nova-tech.dk`). `api/` is untouched.

**Reused verbatim from `c081267` (restore, no logic change):**
- `package.json`, `astro.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `.vscode/*`
- `public/favicon.svg`
- `src/styles/global.css` — full design system
- `src/lib/auth.ts`, `src/pages/login.astro`, `src/pages/logout.ts`
- `tests/auth.test.ts`, `tests/dates.test.ts`

**Reused with small adaptation:**
- `src/components/Layout.astro` — nav links only
- `src/components/Nav.astro` — new link set
- `src/middleware.ts` — unchanged logic (verify it still compiles without D1)
- `src/lib/dates.ts` — keep `mondayOf/addDaysISO/formatDa/dayMonthDa/isoWeek/nextWeekStart/WEEKDAYS_DA`; drop nothing needed, trim only `weekStatus` if unused
- `src/components/MealCard.astro` — restructure to dish model (see Task 5)

**New files:**
- `src/lib/api.ts` — typed server-only REST client (Task 3)
- `src/lib/api.types.ts` — response/request types mirroring backend (Task 3)
- `src/components/DishPicker.astro` — combobox with inline create (Task 5)
- `src/pages/index.astro` — Forside (Task 8)
- `src/pages/madplan/index.astro` — Ugeplan (Task 5)
- `src/pages/forslag.astro` — Forslag (Task 6)
- `src/pages/retter.astro` — Ret-katalog (Task 7)
- BFF routes under `src/pages/api/`: `day.ts`, `dishes.ts`, `suggestions/accept.ts`, `suggestions/refresh.ts`, `suggestions/poll.ts` (Tasks 5–7)
- `tests/api.test.ts`, `tests/accept-week.test.ts` (Tasks 3, 6)
- `src/lib/accept-week.ts` — pure skip-filter for "accept whole week" (Task 6)

**Deleted (must not exist after Task 2):** `src/lib/db.ts`, `src/lib/weekplan.ts`, `src/lib/prices.ts`, `src/lib/locations.ts`, `src/lib/nemlig/*`, `src/pages/beholdning.astro`, `src/pages/priser.astro`, `src/pages/import.astro`, `src/pages/madplan/arkiv.astro`, `src/pages/api/meals.ts`, `src/pages/api/inventory.ts`, `src/pages/api/import.ts`, `src/components/ItemCard.astro`, `migrations/`, `worker-configuration.d.ts` (regenerate), and D1 config in `wrangler.jsonc`. (locations/nemlig return in Spec B — restore then.)

---

## Task 1: Restore Astro scaffold + design system, strip D1 config

**Files:**
- Restore: `package.json`, `astro.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `public/favicon.svg`, `src/styles/global.css`, `src/lib/auth.ts`, `src/lib/dates.ts`, `src/pages/login.astro`, `src/pages/logout.ts`, `src/middleware.ts`, `tests/auth.test.ts`, `tests/dates.test.ts`
- Modify: `wrangler.jsonc` (remove D1), `.gitignore` (add node_modules/dist/.astro if missing)

**Interfaces:**
- Produces: working `npm run build` + `npm test` (auth/dates green); `wrangler.jsonc` with no D1.

- [ ] **Step 1: Restore the reused files from git history**

```bash
cd /c/Users/mikey/Documents/nova-madplan
for f in package.json astro.config.mjs tsconfig.json vitest.config.ts \
  public/favicon.svg src/styles/global.css src/lib/auth.ts src/lib/dates.ts \
  src/pages/login.astro src/pages/logout.ts src/middleware.ts \
  tests/auth.test.ts tests/dates.test.ts .vscode/extensions.json .vscode/launch.json; do
  mkdir -p "$(dirname "$f")"
  git show "c081267:$f" > "$f"
done
```

- [ ] **Step 2: Restore then rewrite `wrangler.jsonc` without D1**

Restore the old one, then replace its contents so no `d1_databases` block remains:

```jsonc
{
	"$schema": "./node_modules/wrangler/config-schema.json",
	"compatibility_date": "2026-06-17",
	"compatibility_flags": ["global_fetch_strictly_public"],
	"name": "madplan",
	"main": "@astrojs/cloudflare/entrypoints/server",
	"routes": [
		{ "pattern": "madplan.nova-tech.dk", "custom_domain": true }
	],
	"assets": {
		"directory": "./dist",
		"binding": "ASSETS"
	},
	"observability": {
		"enabled": true
	}
}
```

- [ ] **Step 3: Ensure `.gitignore` covers node build artifacts**

Read `.gitignore`; if `node_modules`, `dist`, or `.astro` are missing, append them. (`.wrangler/` is already ignored per repo status.)

- [ ] **Step 4: Install and verify build + tests**

Run:
```bash
npm install
npm test
npm run build
```
Expected: `npm test` PASSES `tests/auth.test.ts` and `tests/dates.test.ts`; `npm run build` succeeds (login/logout/middleware compile with no D1 references).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Fase 7: gendan Astro-skelet + design-system, fjern D1-config"
```

---

## Task 2: Remove all dead D1 / lager / pris code

**Files:**
- Delete: `src/lib/db.ts`, `src/lib/weekplan.ts`, `src/lib/prices.ts`, `src/lib/locations.ts`, `src/lib/nemlig/`, `src/pages/beholdning.astro`, `src/pages/priser.astro`, `src/pages/import.astro`, `src/pages/madplan/arkiv.astro`, `src/pages/api/meals.ts`, `src/pages/api/inventory.ts`, `src/pages/api/import.ts`, `src/components/ItemCard.astro`, `src/components/MealCard.astro` (temporarily — rebuilt in Task 5), `migrations/`, `tests/weekplan.test.ts`, `tests/prices.test.ts`, `tests/locations.test.ts`, `tests/nemlig/`, `worker-configuration.d.ts`

**Interfaces:**
- Produces: a tree with only reused-scaffold files; `grep -ri d1 src wrangler.jsonc` empty.

- [ ] **Step 1: Delete dead code**

These files were never restored in Task 1, so most don't exist yet. Confirm and remove any that do:
```bash
rm -rf src/lib/db.ts src/lib/weekplan.ts src/lib/prices.ts src/lib/locations.ts \
  src/lib/nemlig src/pages/beholdning.astro src/pages/priser.astro \
  src/pages/import.astro src/pages/madplan/arkiv.astro src/pages/api \
  src/components/ItemCard.astro src/components/MealCard.astro migrations \
  tests/weekplan.test.ts tests/prices.test.ts tests/locations.test.ts \
  tests/nemlig worker-configuration.d.ts 2>/dev/null; true
```

- [ ] **Step 2: Regenerate Cloudflare worker types (no D1 binding)**

Run: `npm run generate-types` (writes a fresh `worker-configuration.d.ts` with `SITE_PASSWORD`, `MADPLAN_API_BASE`, `LIFEHUB_API_TOKEN` env — see Task 3 Step 1 for adding them to `wrangler.jsonc` vars first if the command needs them). If it errors on missing vars, skip until Task 3 and note it.

- [ ] **Step 3: Verify no D1 references remain**

Run: `grep -ri d1 src wrangler.jsonc || echo EMPTY`
Expected: `EMPTY`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Fase 7: fjern al D1/lager/pris-kode (død kode ud)"
```

---

## Task 3: Datalayer — typed BFF REST client (`api.ts`)

**Files:**
- Create: `src/lib/api.types.ts`, `src/lib/api.ts`, `tests/api.test.ts`

**Interfaces:**
- Consumes: `MADPLAN_API_BASE`, `LIFEHUB_API_TOKEN` from `cloudflare:workers` env.
- Produces (exact signatures later tasks rely on):
  - Types in `api.types.ts`: `DayStatus = 'planned'|'cooked'|'skipped'|'empty'`; `Day{date:string,weekday:string,dish_id:number|null,dish_name:string|null,status:DayStatus,note:string|null}`; `WeekPlan{week_start:string,days:Day[],updated_at:string}`; `Ingredient{name:string,qty?:number|null,unit?:string|null}`; `Dish{id:number,name:string,tags:string[],recurring_weekly:boolean,ingredients:Ingredient[],last_made:string|null,active:boolean}`; `DishInput{name:string,tags?:string[],recurring_weekly?:boolean,ingredients?:Ingredient[],active?:boolean}`; `Suggestion{date:string,dish_id:number,dish_name:string,reason:string,confidence:number}`; `SuggestionSet{week_start:string,generated_by:string,quality:'fast'|'reviewed',inventory_hash:string|null,suggestions:Suggestion[],updated_at:string}`.
  - `class ApiError extends Error { status:number; detail:string }`
  - `makeApi(base:string, token:string, fetchImpl?:typeof fetch)` returns object with: `getCurrentWeekplan():Promise<WeekPlan>`, `getWeekplan(start:string):Promise<WeekPlan>`, `putDay(b:{date:string;status:DayStatus;dish_id:number|null;note:string|null}):Promise<WeekPlan>`, `listDishes(includeInactive?:boolean):Promise<Dish[]>`, `createDish(b:DishInput):Promise<Dish>`, `updateDish(id:number,b:Partial<DishInput>):Promise<Dish>`, `deleteDish(id:number):Promise<void>`, `getSuggestions():Promise<SuggestionSet>`, `refreshSuggestions():Promise<void>`, `acceptSuggestion(date:string,dish_id:number):Promise<WeekPlan>`.
  - `getApi()` — reads env via `cloudflare:workers` and returns `makeApi(...)`. Pages/routes call `getApi()`.

- [ ] **Step 1: Add env vars to `wrangler.jsonc` for local dev typing**

Add a `vars` block (dev placeholders only — real values are Pages secrets; do NOT put the real token here):
```jsonc
	"vars": {
		"MADPLAN_API_BASE": "http://localhost:8400",
		"LIFEHUB_API_TOKEN": "dev",
		"SITE_PASSWORD": "dev"
	}
```
Then run `npm run generate-types`.

- [ ] **Step 2: Write the failing test**

`tests/api.test.ts` — `makeApi` is pure (takes `fetchImpl`), so testable without Cloudflare:
```ts
import { describe, it, expect, vi } from 'vitest';
import { makeApi, ApiError } from '../src/lib/api';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

describe('makeApi', () => {
  it('GET current weekplan sends bearer and parses body', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ week_start: '2026-07-06', days: [], updated_at: 'x' }));
    const api = makeApi('http://b', 'secret', fetchImpl as unknown as typeof fetch);
    const wp = await api.getCurrentWeekplan();
    expect(wp.week_start).toBe('2026-07-06');
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://b/api/weekplan/current');
    expect((init as RequestInit).headers).toMatchObject({ Authorization: 'Bearer secret' });
  });

  it('putDay POSTs JSON to /api/weekplan/day', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ week_start: 'w', days: [], updated_at: 'x' }));
    const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
    await api.putDay({ date: '2026-07-06', status: 'planned', dish_id: 17, note: null });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://b/api/weekplan/day');
    expect((init as RequestInit).method).toBe('PUT');
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({ dish_id: 17, status: 'planned' });
  });

  it('deleteDish issues DELETE and tolerates 204 empty body', async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 204 }));
    const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
    await expect(api.deleteDish(3)).resolves.toBeUndefined();
    expect((fetchImpl.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
  });

  it('throws ApiError with status+detail on non-2xx', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ detail: 'Dish 99 not found' }, 404));
    const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
    await expect(api.getSuggestions()).rejects.toMatchObject({ status: 404, detail: 'Dish 99 not found' } satisfies Partial<ApiError>);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run tests/api.test.ts`
Expected: FAIL — cannot import `makeApi`.

- [ ] **Step 4: Implement `api.types.ts` and `api.ts`**

`src/lib/api.types.ts`: the interfaces/types listed in Interfaces above.

`src/lib/api.ts`:
```ts
import type { WeekPlan, Dish, DishInput, SuggestionSet, DayStatus } from './api.types';
export type * from './api.types';

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = 'ApiError';
  }
}

export function makeApi(base: string, token: string, fetchImpl: typeof fetch = fetch) {
  const root = base.replace(/\/$/, '');
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetchImpl(`${root}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init.body ? { 'content-type': 'application/json' } : {}),
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = ((await res.json()) as { detail?: string }).detail ?? detail; } catch { /* non-JSON */ }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  return {
    getCurrentWeekplan: () => call<WeekPlan>('/api/weekplan/current'),
    getWeekplan: (start: string) => call<WeekPlan>(`/api/weekplan?start=${encodeURIComponent(start)}`),
    putDay: (b: { date: string; status: DayStatus; dish_id: number | null; note: string | null }) =>
      call<WeekPlan>('/api/weekplan/day', { method: 'PUT', body: JSON.stringify(b) }),
    listDishes: (includeInactive = true) =>
      call<Dish[]>(`/api/dishes?include_inactive=${includeInactive}`),
    createDish: (b: DishInput) => call<Dish>('/api/dishes', { method: 'POST', body: JSON.stringify(b) }),
    updateDish: (id: number, b: Partial<DishInput>) =>
      call<Dish>(`/api/dishes/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
    deleteDish: (id: number) => call<void>(`/api/dishes/${id}`, { method: 'DELETE' }),
    getSuggestions: () => call<SuggestionSet>('/api/suggestions/current'),
    refreshSuggestions: () => call<void>('/api/suggestions/refresh', { method: 'POST' }),
    acceptSuggestion: (date: string, dish_id: number) =>
      call<WeekPlan>('/api/suggestions/accept', { method: 'POST', body: JSON.stringify({ date, dish_id }) }),
  };
}
```

`getApi()` in a separate spot to keep `makeApi` env-free — add at the bottom of `api.ts`:
```ts
export async function getApi() {
  const { env } = await import('cloudflare:workers');
  return makeApi(env.MADPLAN_API_BASE, env.LIFEHUB_API_TOKEN);
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run tests/api.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Fase 7: typet BFF REST-klient (api.ts) mod ny backend"
```

---

## Task 4: Layout + Nav shell against new routes

**Files:**
- Modify: `src/components/Nav.astro`, `src/components/Layout.astro`

**Interfaces:**
- Produces: nav rendering links Forside/Madplan/Forslag/Retter; used by all pages.

- [ ] **Step 1: Update `Nav.astro` link set**

Replace the `links` array (keep the existing markup/styling and `isActive` logic):
```ts
const links: { href: string; label: string }[] = [
  { href: '/', label: 'Forside' },
  { href: '/madplan', label: 'Madplan' },
  { href: '/forslag', label: 'Forslag' },
  { href: '/retter', label: 'Retter' },
];
```
Update `isActive` so `/madplan` matches `path === '/madplan'` or `path.startsWith('/madplan')`; others use `startsWith`.

- [ ] **Step 2: Verify Layout still imports Nav + global.css unchanged**

Read `Layout.astro`; no change needed beyond confirming it compiles. Keep the theme-toggle script.

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: succeeds (pages referenced by nav don't exist yet — that's fine; build only fails on broken imports, not dead links).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Fase 7: opdatér nav til nye ruter"
```

---

## Task 5: Ugeplan screen + DishPicker + day BFF route

**Files:**
- Create: `src/components/DishPicker.astro`, `src/components/MealCard.astro` (rebuilt), `src/pages/madplan/index.astro`, `src/pages/api/day.ts`
- Reference: old `MealCard.astro` (`git show c081267:src/components/MealCard.astro`) for styling to reuse.

**Interfaces:**
- Consumes: `getApi()`, `WeekPlan`, `Day`, `Dish` from Task 3; `mondayOf`, `addDaysISO`, `dayMonthDa`, `formatDa` from `dates.ts`.
- Produces: `/madplan?start=YYYY-MM-DD` renders the week; day form posts to `/api/day`.

- [ ] **Step 1: Write the day BFF route `src/pages/api/day.ts`**

Handles set-dish (with optional inline create), clear, mark cooked/skipped. Session is enforced by `middleware.ts`.
```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
import type { DayStatus } from '../../lib/api.types';

function s(d: FormData, k: string): string { return String(d.get(k) ?? '').trim(); }

export const POST: APIRoute = async ({ request, redirect }) => {
  const api = await getApi();
  const data = await request.formData();
  const date = s(data, 'date');
  const status = (s(data, 'status') || 'planned') as DayStatus;
  const note = s(data, 'note') || null;
  const back = `/madplan?start=${s(data, 'week_start') || date}`;

  let dishId: number | null = null;
  if (status !== 'empty') {
    const existing = s(data, 'dish_id');
    const newName = s(data, 'new_dish_name');
    if (existing) dishId = Number(existing);
    else if (newName) dishId = (await api.createDish({ name: newName })).id;
  }
  try {
    await api.putDay({ date, status, dish_id: dishId, note });
  } catch (e) {
    return redirect(`${back}&error=1`);
  }
  return redirect(back);
};
```

- [ ] **Step 2: Build `DishPicker.astro`**

A `<datalist>`-backed combobox: search existing active dishes, or type a new name. Uses one text input bound to a datalist plus a hidden resolver in the form submit. Minimal, progressive-enhancement friendly:
```astro
---
import type { Dish } from '../lib/api.types';
interface Props { dishes: Dish[]; date: string; }
const { dishes, date } = Astro.props;
const listId = `dishes-${date}`;
---
<datalist id={listId}>
  {dishes.map((d) => <option value={d.name} data-id={d.id}></option>)}
</datalist>
<input class="dish-input" list={listId} name="dish_name_display" placeholder="søg eller skriv ny ret…" autocomplete="off" />
<input type="hidden" name="dish_id" value="" />
<input type="hidden" name="new_dish_name" value="" />
<script is:inline define:vars={{ listId }}>
  (function () {
    var form = document.currentScript.closest('form');
    if (!form) return;
    form.addEventListener('submit', function () {
      var disp = form.querySelector('input[name="dish_name_display"]');
      var list = document.getElementById(listId);
      var hiddenId = form.querySelector('input[name="dish_id"]');
      var hiddenNew = form.querySelector('input[name="new_dish_name"]');
      var val = (disp && disp.value || '').trim();
      var match = list && Array.prototype.find.call(list.options, function (o) { return o.value === val; });
      if (match) { hiddenId.value = match.getAttribute('data-id'); hiddenNew.value = ''; }
      else { hiddenId.value = ''; hiddenNew.value = val; }
    });
  })();
</script>
```

- [ ] **Step 3: Rebuild `MealCard.astro` against the Day model**

Restore the old file's `<style>` block verbatim (reuse the card styling). Replace the frontmatter/markup to use `Day` + `DishPicker` + status actions (planned/cooked/skipped/empty), dropping `is_flex`/`cook`/`recipe_url`. Each action is a small `form method="post" action="/api/day"` carrying hidden `date`, `week_start`, `status`. "Markér tilberedt" submits `status=cooked` with the current `dish_id`. "Ryd" submits `status=empty`.
```astro
---
import type { Day, Dish } from '../lib/api.types';
import DishPicker from './DishPicker.astro';
import { dayMonthDa } from '../lib/dates';
interface Props { day: Day; dishes: Dish[]; weekStart: string; readOnly?: boolean; }
const { day, dishes, weekStart, readOnly = false } = Astro.props;
const planned = day.status === 'planned' || day.status === 'cooked';
const state = day.status === 'cooked' ? 'cooked' : planned ? 'planned' : 'empty';
---
<div class={`card meal meal-${state}`}>
  <div class="row spread">
    <span class="meal-day">{day.weekday}</span>
    <span class="tag">{dayMonthDa(day.date)}</span>
  </div>
  <div class="meal-body">
    {day.dish_name && <div class="meal-title">{day.status === 'cooked' ? '✅ ' : ''}{day.dish_name}</div>}
    {!day.dish_name && <div class="meal-empty">Ingen plan endnu</div>}
    {day.note && <div class="small muted">{day.note}</div>}
    {day.status === 'skipped' && <div class="small muted">Sprunget over</div>}
  </div>
  {!readOnly && (
    <div class="meal-actions">
      <details class="meal-edit">
        <summary class="edit-toggle">{planned ? '✏️ Redigér' : '+ Tilføj ret'}</summary>
        <form method="post" action="/api/day" class="meal-edit-form">
          <input type="hidden" name="date" value={day.date} />
          <input type="hidden" name="week_start" value={weekStart} />
          <input type="hidden" name="status" value="planned" />
          <div class="field"><label>Ret</label><DishPicker dishes={dishes} date={day.date} /></div>
          <div class="field"><label>Note (valgfri)</label><input name="note" value={day.note ?? ''} /></div>
          <button class="btn-primary btn-block" type="submit">Gem</button>
        </form>
      </details>
      {planned && (
        <form method="post" action="/api/day">
          <input type="hidden" name="date" value={day.date} />
          <input type="hidden" name="week_start" value={weekStart} />
          <input type="hidden" name="status" value="cooked" />
          <input type="hidden" name="dish_id" value={day.dish_id ?? ''} />
          <button class="btn-sm" type="submit">Markér tilberedt</button>
        </form>
      )}
      {day.status !== 'empty' && (
        <form method="post" action="/api/day">
          <input type="hidden" name="date" value={day.date} />
          <input type="hidden" name="week_start" value={weekStart} />
          <input type="hidden" name="status" value="empty" />
          <button class="btn-sm" type="submit">Ryd</button>
        </form>
      )}
    </div>
  )}
</div>
<style>/* PASTE the <style> block from git show c081267:src/components/MealCard.astro verbatim, minus .meal-flex if unused */</style>
```
Note: when marking cooked, the backend requires the day already have a dish; `day.dish_id` is passed. If `dish_id` is null the button isn't rendered (only shown when `planned`).

- [ ] **Step 4: Build the Ugeplan page `src/pages/madplan/index.astro`**

Week nav via `?start=`; defaults to current week. Fetches weekplan + active dishes; tolerant error banner.
```astro
---
import Layout from '../../components/Layout.astro';
import MealCard from '../../components/MealCard.astro';
import { getApi, ApiError } from '../../lib/api';
import { mondayOf, addDaysISO, dayMonthDa } from '../../lib/dates';
import type { WeekPlan, Dish } from '../../lib/api.types';

const startParam = Astro.url.searchParams.get('start');
const hasError = Astro.url.searchParams.get('error') === '1';
const api = await getApi();
let plan: WeekPlan | null = null;
let dishes: Dish[] = [];
let loadError = '';
try {
  plan = startParam ? await api.getWeekplan(startParam) : await api.getCurrentWeekplan();
  dishes = (await api.listDishes(false));
} catch (e) {
  loadError = e instanceof ApiError ? `Kunne ikke hente madplanen (${e.status}).` : 'Kunne ikke nå madplan-tjenesten.';
}
const ws = plan?.week_start ?? mondayOf(new Date());
const prev = addDaysISO(ws, -7);
const next = addDaysISO(ws, 7);
const range = `${dayMonthDa(ws)} – ${dayMonthDa(addDaysISO(ws, 6))}`;
---
<Layout title="Madplan">
  <h1>Madplan</h1>
  {hasError && <p class="notice">Handlingen kunne ikke gennemføres. Prøv igen.</p>}
  {loadError && <p class="notice">{loadError}</p>}
  <div class="section-head">
    <a class="count-pill" href={`/madplan?start=${prev}`}>‹ Forrige</a>
    <h2>{range}</h2>
    <a class="count-pill" href={`/madplan?start=${next}`}>Næste ›</a>
  </div>
  {plan && (
    <div class="cards">
      {plan.days.map((d) => <MealCard day={d} dishes={dishes} weekStart={ws} />)}
    </div>
  )}
</Layout>
```

- [ ] **Step 5: Manual smoke build**

Run: `npm run build`
Expected: succeeds. (End-to-end behavior is verified at deploy per §3.5; no unit test for Astro pages.)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Fase 7: ugeplan-skærm med uge-navigation, dish-picker og cooked"
```

---

## Task 6: Forslag screen + accept-week logic + suggestion BFF routes

**Files:**
- Create: `src/lib/accept-week.ts`, `tests/accept-week.test.ts`, `src/pages/forslag.astro`, `src/pages/api/suggestions/accept.ts`, `src/pages/api/suggestions/refresh.ts`, `src/pages/api/suggestions/poll.ts`

**Interfaces:**
- Consumes: `getApi`, `SuggestionSet`, `WeekPlan`, `Suggestion` from Task 3.
- Produces: `daysToAccept(suggestions, weekplan)` → `Suggestion[]` skipping planned/cooked days; `/forslag` page; poll endpoint returning `{updated_at}`.

- [ ] **Step 1: Write the failing test for `accept-week.ts`**

`tests/accept-week.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { daysToAccept } from '../src/lib/accept-week';
import type { SuggestionSet, WeekPlan } from '../src/lib/api.types';

const sugg = (date: string, dish_id: number) => ({ date, dish_id, dish_name: 'x', reason: 'r', confidence: 0.5 });
const day = (date: string, status: string) => ({ date, weekday: 'x', dish_id: 1, dish_name: 'd', status, note: null });

describe('daysToAccept', () => {
  it('skips days already planned or cooked; keeps empty/skipped', () => {
    const set = { suggestions: [sugg('2026-07-13', 3), sugg('2026-07-14', 4), sugg('2026-07-15', 5)] } as SuggestionSet;
    const wp = { days: [day('2026-07-13', 'planned'), day('2026-07-14', 'cooked'), day('2026-07-15', 'empty')] } as unknown as WeekPlan;
    const out = daysToAccept(set, wp);
    expect(out.map((s) => s.date)).toEqual(['2026-07-15']);
  });

  it('accepts all when weekplan has no matching planned days', () => {
    const set = { suggestions: [sugg('2026-07-13', 3)] } as SuggestionSet;
    const wp = { days: [day('2026-07-13', 'skipped')] } as unknown as WeekPlan;
    expect(daysToAccept(set, wp)).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run tests/accept-week.test.ts`
Expected: FAIL — `daysToAccept` not found.

- [ ] **Step 3: Implement `src/lib/accept-week.ts`**

```ts
import type { SuggestionSet, WeekPlan, Suggestion } from './api.types';

/** Menneske-vinder (§2.4): spring dage over der allerede er planned/cooked. */
export function daysToAccept(set: SuggestionSet, plan: WeekPlan): Suggestion[] {
  const locked = new Set(
    plan.days.filter((d) => d.status === 'planned' || d.status === 'cooked').map((d) => d.date),
  );
  return set.suggestions.filter((s) => !locked.has(s.date));
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npx vitest run tests/accept-week.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the BFF routes**

`src/pages/api/suggestions/refresh.ts`:
```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
export const POST: APIRoute = async () => {
  const api = await getApi();
  try { await api.refreshSuggestions(); return new Response(JSON.stringify({ status: 'accepted' }), { status: 202 }); }
  catch (e) { return new Response(JSON.stringify({ status: 'error' }), { status: 502 }); }
};
```
`src/pages/api/suggestions/poll.ts` (client polls this to detect `updated_at` change):
```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
export const GET: APIRoute = async () => {
  const api = await getApi();
  try { const s = await api.getSuggestions(); return new Response(JSON.stringify({ updated_at: s.updated_at }), { status: 200 }); }
  catch { return new Response(JSON.stringify({ updated_at: null }), { status: 502 }); }
};
```
`src/pages/api/suggestions/accept.ts` — accepts one day (form) OR the whole week (`all=1`):
```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
import { daysToAccept } from '../../../lib/accept-week';
function s(d: FormData, k: string): string { return String(d.get(k) ?? '').trim(); }
export const POST: APIRoute = async ({ request, redirect }) => {
  const api = await getApi();
  const data = await request.formData();
  try {
    if (s(data, 'all') === '1') {
      const [set, plan] = [await api.getSuggestions(), await api.getCurrentWeekplanForWeek(s(data, 'week_start'))];
      for (const sug of daysToAccept(set, plan)) await api.acceptSuggestion(sug.date, sug.dish_id);
    } else {
      await api.acceptSuggestion(s(data, 'date'), Number(s(data, 'dish_id')));
    }
  } catch { return redirect('/forslag?error=1'); }
  return redirect('/forslag');
};
```
Note: add helper `getCurrentWeekplanForWeek(start:string)` to `api.ts` as `getWeekplan(start)` — reuse existing `getWeekplan`; replace the call above with `await api.getWeekplan(s(data, 'week_start'))`.

- [ ] **Step 6: Build the `/forslag` page**

Shows the set (date, dish, reason, confidence, quality badge), per-day Accept, global Accept-week + Genberegn with client poll.
```astro
---
import Layout from '../components/Layout.astro';
import { getApi, ApiError } from '../lib/api';
import { dayMonthDa } from '../lib/dates';
import type { SuggestionSet } from '../lib/api.types';
const api = await getApi();
let set: SuggestionSet | null = null; let err = '';
try { set = await api.getSuggestions(); }
catch (e) { err = e instanceof ApiError ? `Kunne ikke hente forslag (${e.status}).` : 'Kunne ikke nå tjenesten.'; }
---
<Layout title="Forslag">
  <h1>Forslag</h1>
  {err && <p class="notice">{err}</p>}
  {set && (
    <>
      <div class="section-head">
        <h2>Næste uge · {set.week_start}</h2>
        <span class="tag">{set.quality === 'reviewed' ? '⭐ Gennemgået' : 'Hurtig'}</span>
      </div>
      <div class="row" style="gap:0.5rem; margin-bottom:0.8rem;">
        <form method="post" action="/api/suggestions/accept">
          <input type="hidden" name="all" value="1" />
          <input type="hidden" name="week_start" value={set.week_start} />
          <button class="btn-primary" type="submit">Accepter hele ugen</button>
        </form>
        <button id="recompute" class="btn-sm" type="button">Genberegn</button>
        <span id="recompute-status" class="small muted"></span>
      </div>
      {set.suggestions.length === 0 && <p class="empty">Ingen forslag endnu. Tryk Genberegn.</p>}
      <div class="cards">
        {set.suggestions.map((s) => (
          <div class="card">
            <div class="row spread"><strong>{s.dish_name}</strong><span class="tag">{dayMonthDa(s.date)}</span></div>
            <div class="small muted">{s.reason}</div>
            <div class="small">Sikkerhed: {Math.round(s.confidence * 100)}%</div>
            <form method="post" action="/api/suggestions/accept" style="margin-top:0.5rem;">
              <input type="hidden" name="date" value={s.date} />
              <input type="hidden" name="dish_id" value={s.dish_id} />
              <button class="btn-sm" type="submit">Accepter</button>
            </form>
          </div>
        ))}
      </div>
    </>
  )}
  <script is:inline define:vars={{ before: set?.updated_at ?? '' }}>
    (function () {
      var btn = document.getElementById('recompute');
      var status = document.getElementById('recompute-status');
      if (!btn) return;
      btn.addEventListener('click', async function () {
        btn.disabled = true;
        status.textContent = 'Arbejder… (7b på CPU kan tage 1–2 min)';
        try {
          await fetch('/api/suggestions/refresh', { method: 'POST' });
          var started = Date.now();
          var timer = setInterval(async function () {
            if (Date.now() - started > 180000) { clearInterval(timer); status.textContent = 'Tog for lang tid — genindlæs siden.'; btn.disabled = false; return; }
            var r = await fetch('/api/suggestions/poll');
            var j = await r.json();
            if (j.updated_at && j.updated_at !== before) { clearInterval(timer); status.textContent = 'Færdig — genindlæser…'; location.reload(); }
          }, 5000);
        } catch (e) { status.textContent = 'Kunne ikke starte genberegning.'; btn.disabled = false; }
      });
    })();
  </script>
</Layout>
```

- [ ] **Step 7: Build**

Run: `npm run build && npx vitest run`
Expected: build succeeds; all tests pass.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Fase 7: forslag-skærm med accepter/accepter-uge/genberegn-poll"
```

---

## Task 7: Ret-katalog screen + dishes BFF route

**Files:**
- Create: `src/pages/retter.astro`, `src/pages/api/dishes.ts`

**Interfaces:**
- Consumes: `getApi`, `Dish`, `DishInput` from Task 3.
- Produces: `/retter` CRUD page; `/api/dishes` route handling create/update/delete/toggle actions.

- [ ] **Step 1: Write the dishes BFF route `src/pages/api/dishes.ts`**

```ts
import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
function s(d: FormData, k: string): string { return String(d.get(k) ?? '').trim(); }
export const POST: APIRoute = async ({ request, redirect }) => {
  const api = await getApi();
  const data = await request.formData();
  const action = s(data, 'action');
  try {
    if (action === 'create') {
      await api.createDish({ name: s(data, 'name'), recurring_weekly: s(data, 'recurring_weekly') === '1' });
    } else if (action === 'update') {
      const id = Number(s(data, 'id'));
      await api.updateDish(id, { name: s(data, 'name'), recurring_weekly: s(data, 'recurring_weekly') === '1' });
    } else if (action === 'toggle') {
      await api.updateDish(Number(s(data, 'id')), { active: s(data, 'active') === '1' });
    } else if (action === 'delete') {
      await api.deleteDish(Number(s(data, 'id')));
    }
  } catch { return redirect('/retter?error=1'); }
  return redirect('/retter');
};
```
Note: reactivate uses `toggle` with `active=1` (PUT active:true); soft-delete uses `delete` (DELETE → active=0).

- [ ] **Step 2: Build the `/retter` page**

Lists dishes (active + inactive), inline add form, per-dish recurring toggle + active toggle + delete. Reuse `card`/`btn` styles from `global.css`.
```astro
---
import Layout from '../components/Layout.astro';
import { getApi, ApiError } from '../lib/api';
import type { Dish } from '../lib/api.types';
const api = await getApi();
let dishes: Dish[] = []; let err = '';
try { dishes = await api.listDishes(true); }
catch (e) { err = e instanceof ApiError ? `Kunne ikke hente retter (${e.status}).` : 'Kunne ikke nå tjenesten.'; }
---
<Layout title="Retter">
  <h1>Ret-katalog</h1>
  {err && <p class="notice">{err}</p>}
  <form method="post" action="/api/dishes" class="card">
    <input type="hidden" name="action" value="create" />
    <div class="field"><label>Ny ret</label><input name="name" required placeholder="fx Tacos" /></div>
    <label class="row" style="gap:0.5rem;"><input type="checkbox" name="recurring_weekly" value="1" style="width:auto;" /> Fast ugentlig ret</label>
    <button class="btn-primary btn-block" type="submit" style="margin-top:0.5rem;">Tilføj ret</button>
  </form>
  <div class="cards" style="margin-top:1rem;">
    {dishes.map((d) => (
      <div class={`card ${d.active ? '' : 'muted'}`}>
        <div class="row spread">
          <strong>{d.name}</strong>
          {d.recurring_weekly && <span class="tag">Fast</span>}
        </div>
        {d.last_made && <div class="small muted">Sidst lavet: {d.last_made}</div>}
        {!d.active && <div class="small muted">Inaktiv</div>}
        <div class="meal-actions">
          <form method="post" action="/api/dishes">
            <input type="hidden" name="action" value="toggle" />
            <input type="hidden" name="id" value={d.id} />
            <input type="hidden" name="active" value={d.active ? '0' : '1'} />
            <button class="btn-sm" type="submit">{d.active ? 'Deaktivér' : 'Aktivér'}</button>
          </form>
          <form method="post" action="/api/dishes">
            <input type="hidden" name="action" value="toggle" />
            <input type="hidden" name="id" value={d.id} />
            {/* recurring toggle: flip current value */}
            <input type="hidden" name="active" value={d.active ? '1' : '0'} />
          </form>
        </div>
      </div>
    ))}
  </div>
</Layout>
```
Note: keep the recurring-weekly edit simple — a dedicated small form per dish that submits `action=update` with `name` (unchanged) + `recurring_weekly` flipped. If that is awkward, defer recurring-edit to an "✏️ Redigér" details block mirroring MealCard. Minimum viable: add + active-toggle + delete + recurring shown; recurring-edit via an edit form.

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Fase 7: ret-katalog CRUD med active/recurring"
```

---

## Task 8: Forside + final verification + DEPLOY.md

**Files:**
- Create: `src/pages/index.astro`
- Modify: `docs/DEPLOY.md`

**Interfaces:**
- Consumes: `getApi`, `WeekPlan` from Task 3.

- [ ] **Step 1: Build `src/pages/index.astro`**

Shows current week compactly (readOnly cards) + link to Forslag; tolerant on backend down.
```astro
---
import Layout from '../components/Layout.astro';
import MealCard from '../components/MealCard.astro';
import { getApi, ApiError } from '../lib/api';
import type { WeekPlan } from '../lib/api.types';
const api = await getApi();
let plan: WeekPlan | null = null; let err = '';
try { plan = await api.getCurrentWeekplan(); }
catch (e) { err = e instanceof ApiError ? `Kunne ikke hente ugen (${e.status}).` : 'Kunne ikke nå madplan-tjenesten.'; }
---
<Layout title="Oversigt">
  <h1>Madplan</h1>
  {err && <p class="notice">{err}</p>}
  <div class="section-head">
    <h2>Denne uge</h2>
    <a class="count-pill" href="/madplan">Redigér →</a>
  </div>
  {plan && <div class="cards">{plan.days.map((d) => <MealCard day={d} dishes={[]} weekStart={plan.week_start} readOnly />)}</div>}
  <p class="muted small" style="margin-top:1rem;"><a href="/forslag">Se ugens forslag →</a></p>
</Layout>
```

- [ ] **Step 2: Update `docs/DEPLOY.md` with a Fase 7 section**

Append a "## Fase 7 — Frontend (Cloudflare Pages)" section documenting: the new tunnel public hostname `madplan-api.nova-tech.dk` → `http://localhost:8400` on LXC 103 (same cloudflared config as ha.nova-tech.dk); recommended optional Cloudflare Access policy as hardening; the three Pages env vars (`MADPLAN_API_BASE=https://madplan-api.nova-tech.dk`, `LIFEHUB_API_TOKEN=<same as backend token A>`, `SITE_PASSWORD=<existing>`); and that the old D1 database + binding are decommissioned only AFTER the acceptance criteria pass. Write it in Danish.

- [ ] **Step 3: Full verification pass**

Run:
```bash
npx vitest run
npm run build
grep -ri d1 src wrangler.jsonc || echo "D1 CLEAN"
grep -rn "LIFEHUB_API_TOKEN" dist 2>/dev/null && echo "TOKEN LEAK - FAIL" || echo "NO TOKEN IN BUNDLE"
```
Expected: tests pass; build succeeds; `D1 CLEAN`; `NO TOKEN IN BUNDLE`. (The token only appears in server code that Cloudflare keeps server-side; the `dist` grep is a guard — the client-facing assets live under `dist` and must not contain it.)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Fase 7: forside, DEPLOY-guide og slut-verifikation"
```

---

## Self-Review (completed)

**Spec coverage (Spec A §3):** datalayer api.ts (Task 3) ✓; ugeplan w/ week-nav + dish-picker + cooked (Task 5) ✓; forslag w/ accept + accept-week + refresh-poll (Task 6) ✓; retter CRUD + active + recurring (Task 7) ✓; forside (Task 8) ✓; login/BFF/token-safety (Tasks 1, 3, 8) ✓; remove D1/priser/nemlig-D1 (Task 2) ✓; error tolerance (every page try/catch) ✓; DEPLOY (Task 8) ✓. Acceptance criteria §3.5.1–7 map to Tasks 1/8 (login+token+d1), 5 (weekplan), 6 (accept-week), 8 (verification).

**Deferred to Spec B (out of scope here):** `/beholdning`, nemlig parser, locations, lifehub display.

**Notes for the executor:**
- The MealCard `<style>` block is intentionally not reprinted — copy it verbatim from `git show c081267:src/components/MealCard.astro`.
- Backend must be reachable at `MADPLAN_API_BASE` for pages to render data locally; without it, pages show the friendly error banner (which is itself acceptance criterion §3.5.6).
- If any referenced backend endpoint behaves differently than the contract above, STOP and report (guardrail) — do not modify `api/`.
