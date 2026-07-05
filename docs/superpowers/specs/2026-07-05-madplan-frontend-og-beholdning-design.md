# Design — Madplan-frontend på ny backend + madplan-ejet beholdning (Fase 7 + 8)

> **Status:** godkendt design (brainstorm), afventer implementeringsplan.
> **Kontrakt:** `../../../../lifehub/docs/INTEGRATION_SPEC.md` er stadig autoritativ
> for eksisterende endpoints. Denne fil beskriver frontend-laget + en ny,
> madplan-ejet beholdning. Sprog: dokumentation dansk, kode/API/JSON engelsk.
> **Gammel frontend-kode:** i git-historikken, sidste Astro-commit `c081267`
> ("Add fun fried-egg favicon"). Gendan med `git show c081267:<fil>` pr. fil.

---

## 0. Beslutninger truffet under brainstorm (låst)

1. **Frontend forbliver Astro SSR på Cloudflare Pages** (genbrug projekt + DNS
   `madplan.nova-tech.dk`). Datalag skiftes fra D1-bindings til REST mod ny backend.
2. **BFF-mønster:** browseren taler kun med Astro SSR/Pages Functions; SSR vedhæfter
   `Authorization: Bearer <LIFEHUB_API_TOKEN>` server-side. Token når ALDRIG browseren.
3. **Login uændret:** delt kodeord (`SITE_PASSWORD`) + HMAC-signeret session-cookie.
4. **Dag-planlægning:** dish-picker med **inline hurtig-opret** (søg aktive retter,
   eller skriv ny titel → `POST /api/dishes` → sæt dagen i ét trin).
5. **Uge-navigation:** ‹ forrige / næste › pile på madplan-skærmen (via
   `GET /api/weekplan?start=`). **Ingen separat arkiv-side.**
6. **Beholdning ejes af madplan** (ikke Vikunja). Begrundelse: *indkøbsliste* (to-buy,
   Vikunja/nemlig-kurv) og *beholdning* (stock-on-hand med mængder/noter) er to
   forskellige ting. Familien bruger nemligs egen kurv til at købe ind, så Vikunja
   indgår ikke i madforslag. Reviderer §A3 (§8 tillader det; §2.3 flagged selv
   semantikken som justerbar).
7. **Beholdning eksponeres via `GET /api/inventory`** så både madplans egen
   forslags-motor OG lifehub/brain kan læse den ("LLM'erne har adgang til beholdning").
8. **Lifehub viser kun** beholdning (samlende overblik) — genererer intet; alt dannes
   i madplan.
9. **API-tunnel-hostname:** `madplan-api.nova-tech.dk` → `localhost:8400` (LXC 103).
10. **Ret-opdatering bruger `PUT /api/dishes/{id}`** (backend har PUT, ikke PATCH).

### Rør ALDRIG
- `lifehub/brain/app/review.py`, tabellen `review_queue`, `/api/review/drain` (§0.1).
- Vikunja-indkøbslisten, Telegram-intents, aula — uændret.
- Eksisterende adfærd i forslags-motoren; kun lager-KILDEN ændres (additivt).

---

## 1. Arkitektur

```
Browser ─session─▶ Astro SSR / BFF ─Bearer LIFEHUB_API_TOKEN─▶ madplan-api.nova-tech.dk
       (madplan_session cookie)                                 (retter, ugeplan, forslag, beholdning)

lifehub/brain ─Bearer LIFEHUB_API_TOKEN─▶ madplan  GET /api/inventory   (kun læse → dashboard-visning)
```
Ét backend + ét token for frontend. Ingen brain-tunnel-hostname nødvendig.

---

## 2. Genbrug fra det oprindelige madplan-design (PRIORITET)

Så meget som muligt af `c081267` genbruges — kun datalaget udskiftes. Konkret:

| Gammel fil | Genbrug | Ændring |
|---|---|---|
| `src/styles/global.css` | **Wholesale** | Ingen (hele design-systemet: farver, cards, nav, knapper, lyst/mørkt tema) |
| `src/components/Layout.astro` | Ja | Kun nav-links |
| `src/components/Nav.astro` | Ja | Links: Forside · Madplan · Forslag · Retter · Beholdning |
| `src/pages/login.astro` | **Uændret** | — |
| `src/lib/auth.ts` | **Uændret** | — |
| `src/middleware.ts` | Ja | Uændret session-gate; ryd evt. asset-regex |
| `src/components/MealCard.astro` | Struktur/styling | Datamodel: `title`→dish-picker, `is_flex`→status, dropper cook/recipe_url |
| `src/lib/dates.ts` | Det meste | Behold `mondayOf/addDaysISO/formatDa/dayMonthDa/isoWeek/nextWeekStart`; trim ubrugt |
| `src/lib/nemlig/parser.ts` + `types.ts` + `tests/nemlig/parser.test.ts` | **Wholesale** | Flyt kald til BFF; output POST'es til madplan i stedet for D1 |
| `src/pages/beholdning.astro` | Struktur/styling | Datakilde D1 → `GET /api/inventory`; behold filtre/visning |
| `src/pages/import.astro` | Struktur/flow | Bekræftelses-skærm genbruges; gem → `POST /api/inventory` |
| `src/components/ItemCard.astro` | Ja | Felter mod ny inventory-model |
| `src/lib/locations.ts` | Ja, hvis vi beholder lokationer | Behold som beholdnings-kategorier |
| `public/favicon.svg` | **Uændret** | — |

**Fjernes helt (død kode ud):** `src/lib/db.ts` (D1), `src/lib/weekplan.ts` (fri-tekst
weekplan-parser — erstattes ikke), `src/lib/prices.ts`, `src/pages/priser.astro`,
`src/pages/api/*` (D1-varianter), `migrations/`, `wrangler.jsonc` D1-binding +
`d1_databases`, `worker-configuration.d.ts` D1-typer. `grep -ri d1 src wrangler.jsonc`
skal være tomt.

---

## 3. Spec A — Fase 7: madplan-frontend-port

Selvstændig, deploybar. Ingen backend-ændring. Matcher de oprindelige accept-kriterier.

### 3.1 Datalag — `src/lib/api.ts` (nyt, erstatter `db.ts`)
Server-only typet REST-klient. Læser `MADPLAN_API_BASE` + `LIFEHUB_API_TOKEN` fra
`cloudflare:workers` env (aldrig i klient-bundle). Funktioner 1:1 mod kontrakten:
`getCurrentWeekplan()`, `getWeekplan(start)`, `putDay(body)`, `listDishes(includeInactive?)`,
`getDish(id)`, `createDish(body)`, `updateDish(id, patch)`, `deleteDish(id)`,
`getSuggestions()`, `refreshSuggestions()`, `acceptSuggestion(date, dishId)`.
- Kaster `ApiError{status, detail}`. Pages fanger → **venlig fejlbanner, aldrig hvid
  side**; GET beholder seneste rendering hvor muligt; mutationer → flash-besked.
- Backend-felter (verificeret i `api/app/`): `Day{date,weekday,dish_id,dish_name,
  status(planned|cooked|skipped|empty),note}`; `PUT /api/weekplan/day` body
  `{date,status,dish_id,note}`; `SuggestionSet{week_start,generated_by,quality
  (fast|reviewed),inventory_hash,suggestions[{date,dish_id,dish_name,reason,
  confidence}],updated_at}`; `POST /api/suggestions/accept` body `{date,dish_id}`.

### 3.2 Skærme / ruter
- **`/` Forside:** denne uges plan (kompakt, MealCard readOnly) + genvej til Forslag.
- **`/madplan` Ugeplan:** ‹ uge › pile (GET ?start=), 7 dag-kort. Pr. dag: combobox
  (søg aktive retter + **＋ opret ny ret inline**), ryd dag, markér tilberedt (cooked),
  skipped, frit `note`. Alt via `PUT /api/weekplan/day`. `cooked`/historik/`last_made`
  vedligeholdes server-side — frontend kalder bare PUT.
- **`/forslag` NY:** nyeste SuggestionSet. Pr. dag: dato, ret, begrundelse, confidence,
  `quality`-badge (fast/reviewed), **Accepter** → `POST /api/suggestions/accept`.
  Globalt: **Accepter hele ugen** (BFF-loop pr. dag, springer `planned`/`cooked` over —
  menneske-vinder, §2.4) + **Genberegn** → `POST /api/suggestions/refresh` (202 → vis
  "arbejder…", poll `current` til `updated_at` ændres; forklar at 7b på CPU tager 1–2 min).
- **`/retter` Ret-katalog:** CRUD + `active`-toggle (DELETE = soft delete active=0;
  genaktivér = PUT active:true) + `recurring_weekly`-flag.

### 3.3 BFF-mutations-endpoints (session-gated Astro API-ruter, proxy → backend)
Progressive enhancement: form-POST hvor muligt; fetch til klient-poll/accept-uge.
`POST /api/day`, `/api/dishes` (create/update/delete/toggle),
`/api/suggestions/accept`, `/api/suggestions/refresh`, `GET /api/suggestions/poll`.
Alle kræver session; alle vedhæfter Bearer server-side.

### 3.4 Backend-dikterede reduktioner (ingen backend-ændring)
`is_flex`, `cook`, `recipe_url`, fri-tekst-quickfill, "opret kommende uge" → udgår.
Ét frit `note` pr. dag beholdes.

### 3.5 Accept-kriterier (A)
1. Login med delt kodeord virker; uden session → login-side, ingen data.
2. Ugeplan viser API'ets plan (verificér mandag 2026-07-06 = "Frankfurter m. salat og
   majs", status planned — nås via uge-pilene fra indeværende uge).
3. Accept af forslag → dagen planned; lifehub-dashboard viser samme dag < 10 min.
4. "Accepter hele ugen" rører ikke planned/cooked dage.
5. `LIFEHUB_API_TOKEN` ikke i nogen response/klient-bundle (curl + view-source).
6. Backend stoppet → UI viser fejlbesked, crasher ikke; op igen → virker uden redeploy.
7. `grep -ri d1 src wrangler.jsonc` = tomt.

---

## 4. Spec B — Beholdning (madplan-ejet, end-to-end)

Bygger oven på A. Spænder nova-madplan (backend + frontend) + lifehub (kun visning).

### 4.1 Madplan-backend — nyt `inventory`-modul (`api/app/`)
- **Tabel `inventory_items`:** `id, name, name_key(normaliseret lowercase), quantity,
  unit, note, category/location(nullable), source(nemlig|manuel), added_at, updated_at`.
  Genbrug feltnavne fra gammel D1-model hvor det giver mening.
- **Endpoints (Bearer `LIFEHUB_API_TOKEN`, samme fail-closed-mønster som resten):**
  - `GET /api/inventory` — liste (filtre: q/category). Læses af UI OG lifehub/brain.
  - `POST /api/inventory` — bulk create (nemlig-import + manuel). Merge-på-navn valgfrit.
  - `PATCH /api/inventory/{id}` — opdatér mængde/note/kategori.
  - `DELETE /api/inventory/{id}` — fjern brugt vare.
- **Forslags-motor (ADDITIV):** `api/app/inventory.py::fetch()` peges fra brain-HTTP →
  madplans egen `inventory_items`-tabel. Scoring (§4.2) og alt andet i `suggest.py`
  uændret; kun kilden skifter. `hash_inventory()` beholdes (nu over lokale rækker).
  Ingen ændring af 7b/32b-flow, triggere eller drain.

### 4.2 Madplan-frontend — `/beholdning`
Genbrug `beholdning.astro` + `import.astro` + `ItemCard.astro` + `locations.ts`.
- **Vis nuværende beholdning:** grupperet/søgbar liste med mængder + noter.
- **Nemlig-dump:** paste-felt → **parse i BFF med genbrugt `nemlig/parser.ts`** →
  bekræftelses-skærm (items/opskrifter/ulæselige) → gem → `POST /api/inventory`.
  Parseren bliver browser/BFF-side; backend modtager kun strukturerede varer.
- **Manuel opdatering:** tilføj vare m. note; justér mængde; markér/fjern brugt.
- Nav-menupunkt "Beholdning" peger hertil (ikke længere et Vikunja-link).

### 4.3 Lifehub — kun visning (additiv)
- Dashboard-kort/feed der læser madplans `GET /api/inventory` og viser beholdning.
- Rører intet eksisterende (aula/review/telegram/vikunja/feeds uændret). Følger
  eksisterende feed-cache-mønster med stale-fallback hvis madplan er nede.

### 4.4 Accept-kriterier (B)
1. Nemlig-ordre pastet → parset → gemt → vises i beholdning med mængder.
2. Manuel vare + note gemmes og kan redigeres/fjernes.
3. `GET /api/inventory` returnerer gyldig liste bag Bearer; uden token → 401/403.
4. Forslags-motoren scorer mod madplan-beholdning (verificér: recompute efter
   beholdnings-ændring; `inventory_hash` skifter).
5. Lifehub-dashboard viser beholdningen; madplan nede → stale/venlig fallback.
6. Vikunja-indkøbsliste + Telegram + review beviseligt uændret.

---

## 5. Test (vitest beholdes; TDD på ny ren logik)
- Genbrug: `tests/auth.test.ts`, `tests/dates.test.ts`, `tests/nemlig/parser.test.ts`.
- Nyt (frontend): `api`-klient (mock fetch → mapping/ApiError), accept-uge-skip-filter
  (ren funktion), forslag-poll-logik.
- Nyt (backend, pytest): inventory-CRUD + bulk + `hash_inventory` over lokale rækker +
  motor-repoint (inventory.fetch læser tabel). Følg mønster i `api/tests/`.

---

## 6. DEPLOY.md (tilføjelser — manuelle trin til Mikey)
- **A:** ny tunnel public hostname `madplan-api.nova-tech.dk` → `http://localhost:8400`
  i cloudflared-config på LXC 103 (samme tunnel som ha.nova-tech.dk). Anbefaling:
  valgfri Cloudflare Access-policy som hærdning (Bearer er ellers eneste adgang).
  Pages-secrets: `MADPLAN_API_BASE=https://madplan-api.nova-tech.dk`,
  `LIFEHUB_API_TOKEN=<samme som backend>`, `SITE_PASSWORD=<eksisterende>`.
  D1-database + binding afkobles/slettes EFTER verifikation af accept-kriterierne.
- **B:** ingen ny frontend-infra. Genudrul madplan-api (`docker compose down && up -d`,
  ikke restart) efter backend-ændring; genudrul brain for beholdnings-kortet.

---

## 7. Rækkefølge
Spec A først (lav risiko, får siden live på ny backend, matcher oprindelige
accept-kriterier). Spec B derefter (backend + frontend + lifehub-visning).
Hver spec → egen implementeringsplan → egen PR.

## 8. Åbne detaljer (afklares i planlægning, ellers gælder antagelsen)
- Beholdnings-lokationer/kategorier: genbrug `locations.ts` som frivillig kategori;
  nemlig-parserens `category` mappes hertil. Kan droppes hvis for tungt.
- Merge-på-navn ved nemlig-import (læg mængde til eksisterende vare) — antag ja,
  som gammel `mergeOrInsert`.
- "Kommer ind snart" (Vikunja åbne tasks) indgår IKKE i forslag-scoring (nemlig-kurv
  bruges til indkøb).
