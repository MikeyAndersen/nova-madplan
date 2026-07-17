# nova-madplan — projektoverblik

> **Formål med dette dokument:** hurtig, præcis onboarding for et nyt
> Claude-/udvikler-arbejde. Sprog: dokumentation dansk, kode/API/JSON engelsk.
> Autoritativ integrationskontrakt mod LifeHub: `lifehub/docs/INTEGRATION_SPEC.md`
> (separat repo). Deploy-detaljer: `docs/DEPLOY.md`.

## Hvad det er

Selvstændig **madplan-service** til husstanden — del af **LifeHub**-økosystemet,
men eget repo og egen stack. Mobil-først. Ejer **retter**, **ugeplaner med
historik**, **AI-forslag** og (nyest) **beholdning/lager**.

## Arkitektur — to dele, to maskiner

1. **Backend** (`api/`) — **FastAPI + SQLite**, kører som Docker-container på
   serveren **LXC 103** (host-port `8400` → container `8000`). Indgang
   `api/app/main.py`. Auth: Bearer-token (`LIFEHUB_API_TOKEN`), **fejler lukket**
   uden token. En baggrunds-scheduler (APScheduler) genberegner forslag på et
   lager-poll-interval og natligt kl. 03:00.
2. **Frontend** (repo-rod, `src/`) — **Astro SSR som Cloudflare Worker** på
   `madplan.nova-tech.dk`. Fungerer som **BFF**: browseren ser aldrig
   backend-tokenet. `src/lib/api.ts` sætter Bearer server-side og taler med
   `https://madplan-api.nova-tech.dk` (cloudflared-tunnel til backenden).
   **Adgang til sitet gates af Cloudflare Access i tunnelen** — der er intet
   in-app login (den gamle `SITE_PASSWORD`-model er udgået).

**Sundhedstjek uden token:** `curl https://madplan-api.nova-tech.dk/api/weekplan/current`
→ **401 betyder API'et kører** (tunnel oppe, auth-gated).

## Backend-moduler (`api/app/`)

| Fil | Ansvar |
|---|---|
| `dishes.py` | Ret-katalog: CRUD + soft delete |
| `weekplan.py` | Ugeplaner; `cooked` ⇄ historik ⇄ `last_made` vedligeholdes |
| `inventory.py` | Beholdning (madplan-ejet, `inventory_items`-tabel) |
| `suggestions.py` | Forslags-router (`current`/`refresh`/`accept`) |
| `suggest.py` | Forslags-/drain-motor: 14-dages-regel, lager-scoring, 7b-ranking (Ollama) + deterministisk fallback; 32b-drain |
| `db.py`, `models.py`, `config.py`, `auth.py` | Persistens, skemaer, konfig, token-gate |

Tests: **pytest** i `api/tests/`.

## Datamodel (`src/lib/api.types.ts`)

- **Dish** — `name`, `tags[]`, `recurring_weekly`, `ingredients[]`, `last_made`,
  `active` (soft-delete).
- **WeekPlan** — `week_start` + 7 **Day**s. Day: `status`
  (`planned`|`cooked`|`skipped`|`empty`), `dish_id`/`dish_name`, `note`.
  `cooked`-dage er historik og beskyttes (røres ikke af automatik).
- **SuggestionSet** — AI-forslag for en uge; `quality` `fast`|`reviewed`,
  `inventory_hash`, pr. forslag `reason`/`confidence`.
- **InventoryItem** — lagervare: `name`, `quantity`, `unit`, `category`,
  `source`, `name_key` (til merge-på-navn).

## Frontend-sider (`src/pages/`)

| Rute | Indhold |
|---|---|
| `/` | Forside |
| `/madplan` | Ugeplanen — **kilden til sandhed**. Indeholder quick-import-boksen (`QuickfillPanel.astro`) |
| `/forslag` | **AI-forslag** — maskinens forslag; accepteres pr. dag eller hele ugen |
| `/retter` | Ret-katalog |
| `/beholdning` | Lager (manuel CRUD, forbrug, lokations-gruppering) |
| `/import` | Paste en nemlig-ordre → varer i beholdningen |

BFF-ruter ligger under `src/pages/api/`.

**Sådan spiller siderne sammen:** `/madplan` er sandheden om hvad I spiser. Den
forfattes på tre måder — tast direkte, **paste en `Mandag: ret`-note**
(QuickfillPanel → `/api/weekplan/preview` → `/api/weekplan/apply`), eller
accepter AI-forslag fra `/forslag`. Quick-import kan lade dage stå tomme og lade
"+AI forslag for resten" fylde kun hullerne.

## Forhold til LifeHub (separat repo, ikke i dette workspace)

- madplan ejer retter/planer/forslag **og nu også beholdning** (egen tabel).
- En tjeneste ved navn **brain** (i `lifehub`-repoet, port 8300) poller madplan
  og bygger dashboard-kort.
- Stærkere-model "drain": `POST /api/drain` (token-gated, `MADPLAN_DRAIN_TOKEN`),
  drevet af en PC-agent.
- Autoritativ kontrakt: `lifehub/docs/INTEGRATION_SPEC.md`.

## Deploy (manuelt — se `docs/DEPLOY.md`)

- **Backend:** på LXC 103: `git pull && docker compose down && docker compose up -d --build`
  (kræver SSH — mennesket gør dette; Claude når ikke serveren).
- **Frontend:** `npm run build && npx wrangler deploy` fra PC'en.
- **Rækkefølge er kritisk: API før frontend** (frontenden kalder endpoints der
  skal findes først).

## Arbejdskonventioner (vigtigt for nye sessioner)

- Dansk dokumentation / engelsk kode.
- **Commit og push KUN når mennesket beder om det.**
- Rør **ALDRIG** lifehubs `review.py` / `review_queue` / `/api/review/drain`.
- Ingen rigtige secrets i kode — kun `.env` / Worker-secrets.
- Backend: **pytest**. Frontend: **vitest**.
- `verify`-skill (`.claude/skills/verify/SKILL.md`) kører frontenden mod en lokal
  FastAPI-backend; kræver en gitignoreret `.dev.vars`.

## Status (2026-07-17)

- Feature A (fri-tekst quick-fill) og Feature B (beholdning) er **live**.
- `main` @ `0aa5c3d`, pushet. Seneste UI-ændring (omdøbning
  Forslag → AI-forslag) er pushet men **endnu ikke deployet** til live-sitet.
- Udestående: verifikation af lifehub-siden af Feature B (brain-rebuild +
  dashboard-PWA) — beholdnings-kort på dashboardet.
