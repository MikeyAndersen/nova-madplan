# Deploy — nova-madplan ↔ LifeHub (Fase 1–6) på LXC 103

> **Læs `lifehub/docs/INTEGRATION_SPEC.md` først — autoritativ kontrakt.**
> To repos: `lifehub/` (offentligt) og `nova-madplan/` (privat). Al kode for
> Fase 1–6 er implementeret, verificeret lokalt og pushet til `origin/main`.
> Denne guide dækker selve deployet, som sker manuelt på LXC 103.

## Hvad der er bygget

| Fase | Repo | Indhold |
|---|---|---|
| 1 | nova-madplan | FastAPI+SQLite-service (afløser gammel Astro/Cloudflare-stack); dish/ugeplan-CRUD; D1-migreringsscript |
| 2 | lifehub | brain poller madplans ugeplan → dashboard-kort (begge layouts) + morgen-brief + stale-fallback |
| 3 | lifehub | brain `GET /api/internal/inventory` — Vikunja-indkøb som lager (§2.3, begge buckets) |
| 4 | nova-madplan | Forslags-motor: 14-dages-regel, lager-scoring, 7b-ranking (Ollama) + deterministisk fallback; `/api/suggestions/{current,refresh,accept}`; poll/cron/cooked-triggere |
| 5 | begge | madplan `POST /api/drain` (32b → `reviewed`, menneske-vinder); GPU-agent dræner nu additivt en mål-liste |
| 6 | lifehub | Telegram-genveje ("hvad skal vi have i aften?", "accepter madplanen") som deterministisk fast-path |

## Guardrails (gælder også en Claude der hjælper)

1. **Rør ALDRIG** `brain/app/review.py`, tabellen `review_queue` eller
   `/api/review/drain`. `gpu_agent.py`: kun additivt.
2. Commit/push **kun på besked**. Ingen rigtige secrets i kode — kun `.env`.
3. `.env`-ændringer kræver `docker compose down && up -d` (ikke `restart`).

## Trin for trin

### 0) Hent nyeste kode (bekræft sti; klon hvis de mangler)
```bash
cd /opt/nova-madplan && git pull
cd /opt/lifehub && git pull
```

### 1) Opret det delte netværk (én gang)
```bash
docker network create lifehub_net   # "already exists" er fint
```

### 2) Generér tre tokens
```bash
openssl rand -hex 32   # → <LIFEHUB_API_TOKEN>   (A)
openssl rand -hex 32   # → <INTERNAL_API_TOKEN>  (B)
openssl rand -hex 32   # → <MADPLAN_DRAIN_TOKEN> (C)
```

### 3) Udfyld `.env` i begge repos

Samme værdi hvor angivet — det er hele integrationslimen. `cp .env.example .env`
i hvert repo og udfyld:

| Nøgle | `nova-madplan/.env` | `lifehub/.env` | Skal matche? |
|---|---|---|---|
| `LIFEHUB_API_TOKEN` | `<A>` | `<A>` | **samme** |
| `INTERNAL_API_TOKEN` | `<B>` | `<B>` | **samme** |
| `MADPLAN_URL` | — | `http://madplan-api:8000` | |
| `BRAIN_URL` | `http://brain:8300` | — | |
| `OLLAMA_URL` | `http://ollama:11434` | (findes) | |
| `MADPLAN_DRAIN_TOKEN` | `<C>` | — | matcher PC-agentens `.env` |
| `STRONG_OLLAMA_URL` | PC'ens Ollama (tunnel/LAN) el. tom | — | tom = 32b-drain svarer `online:false` |
| `VIKUNJA_SHOPPING_PROJECT_ID` | — | **id på "Indkøb"-projektet** (spec siger 3) | ⚠️ verificér |

> ⚠️ `VIKUNJA_SHOPPING_PROJECT_ID` styrer hvilket Vikunja-projekt der er "lager"
> (Fase 3). Bekræft det rigtige projekt-id — ellers er lageret tomt.

### 4) Seed madplan-data (valgfrit, anbefalet)

Migrér gamle retter/historik fra den gamle Cloudflare-D1. På en maskine med
wrangler-login (fx PC'en):
```bash
cd nova-madplan && npx wrangler d1 export madplan --remote --output=d1_dump.sql
```
Kopiér `d1_dump.sql` til `/opt/nova-madplan/data/` på serveren, så:
```bash
cd /opt/nova-madplan
docker compose build
docker compose run --rm madplan-api python -m scripts.migrate_d1 --dump /data/d1_dump.sql
# → "Migrated: N dishes, M cooked days …"; lager/priser lægges i CSV ved siden af.
```
Springes over ⇒ tomt ret-katalog (retter kan tilføjes via API/UI senere).
Migreringen afviser at køre hvis db'en allerede har retter (kræver `--force`).

### 5) Byg + start begge stacks
```bash
cd /opt/nova-madplan && docker compose up -d --build
cd /opt/lifehub      && docker compose up -d --build
```

### 6) Verificér (accept-kriterier §7)
```bash
# Fase 1/2 — gyldig §2.2-JSON, 7 dage:
curl -s -H "Authorization: Bearer <A>" http://localhost:8400/api/weekplan/current | jq .

# Fase 3 — lager fra brain (§2.3), set fra madplan-containeren:
docker compose -f /opt/nova-madplan/docker-compose.yml exec madplan-api \
  python -c "import httpx;print(httpx.get('http://brain:8300/api/internal/inventory',headers={'Authorization':'Bearer <B>'}).json())"

# Fase 4 — trig + hent forslag (§2.4):
curl -s -X POST -H "Authorization: Bearer <A>" http://localhost:8400/api/suggestions/refresh
curl -s      -H "Authorization: Bearer <A>" http://localhost:8400/api/suggestions/current | jq .
```

- **Dashboard (Fase 2):** `lifehub/dashboard` er et statisk Astro-build der
  serveres separat (Caddy/nginx) med `PUBLIC_API_BASE` mod brain. Kør
  `cd dashboard && npm ci && npm run build` og udgiv `dist/`. Ugeplan-kortet
  dukker op når brain leverer `madplan`-blokken.
- **Fase 5 (PC-agent):** i PC'ens `agent/.env` tilføj
  `MADPLAN_DRAIN_URL=http://<server-LAN>:8400` og `MADPLAN_DRAIN_TOKEN=<C>`.
  Uden dem dræner agenten kun review (uændret adfærd).
- **Fase 6:** skriv til botten "hvad skal vi have i aften?" og
  "accepter madplanen for næste uge".

## Afvigelser fra spec (begge jf. §8 "ret hvis forkert")

- madplan bruger **`BRAIN_URL=http://brain:8300`** (spec §6 skrev 8000, men
  brain-containeren lytter på 8300).
- Fase 6 er en **deterministisk fast-path** (ikke en LLM-intent-udvidelse) —
  bevidst valg for ikke at røre aula/review-klassificeringen.
- compose blev rettet så **ollama ligger på `lifehub_net`** (ellers kan
  madplan-api ikke nå 7b på `http://ollama:11434`).

## Porte (host → container)

| Service | Host | Container | Net |
|---|---|---|---|
| madplan-api | 8400 | 8000 | lifehub_net |
| brain | 8300 | 8300 | default + lifehub_net |
| ollama | — | 11434 | default + lifehub_net |
| vikunja | 3456 | 3456 | default |

Internt: brain → `http://madplan-api:8000`; madplan → `http://brain:8300` og
`http://ollama:11434`.

## Fase 7 — Frontend (Cloudflare Workers/Pages)

Astro-SSR-frontenden (repo-roden) deployes som Cloudflare Worker på
`madplan.nova-tech.dk` og taler med FastAPI-backenden via en server-side BFF —
browseren ser aldrig backend-tokenet.

### 1) Tunnel-hostname til backenden

På LXC 103 tilføjes et public hostname i den eksisterende cloudflared-config
(samme tunnel som `ha.nova-tech.dk`):

```
madplan-api.nova-tech.dk → http://localhost:8400
```

Valgfri hærdning (anbefalet): læg en Cloudflare Access-policy på
`madplan-api.nova-tech.dk` med en service-token, så kun Workeren kan nå den.
Bearer-tokenet beskytter i forvejen alle endpoints.

### 2) Env vars på Workeren

Sættes som secrets/vars på `madplan`-Workeren (dashboard eller
`wrangler secret put`) — værdierne i `wrangler.jsonc`'s `vars`-blok er kun
dev-pladsholdere:

| Nøgle | Værdi |
|---|---|
| `MADPLAN_API_BASE` | `https://madplan-api.nova-tech.dk` |
| `LIFEHUB_API_TOKEN` | `<A>` — samme som backendens token A |

> **Adgang til sitet håndteres af tunnelen (Cloudflare Access), ikke af appen.**
> `madplan.nova-tech.dk` redirecter uautentificerede til
> `novatechmba.cloudflareaccess.com`. Det tidligere delte kodeord
> (`SITE_PASSWORD` + HMAC-session-cookie) er **udgået** — der findes hverken
> `login.astro`, session-middleware eller nogen `SITE_PASSWORD`-reference i
> `src/`. Sæt den ikke; den gør ingenting. Ældre spec/plan-dokumenter i
> `docs/superpowers/` beskriver stadig den gamle model — de er historik.

### 3) Deploy

```bash
npm ci && npm run build
npx wrangler deploy
```

### 4) Accept-kriterier før oprydning

Den gamle D1-database + binding dekommissioneres **først** når kriterierne i
spec §3.5 er verificeret på det deployede site: Access slipper en igennem,
ugeplanen kan redigeres, forslag kan accepteres (enkeltdag + hel uge),
fejlbanner vises når backenden er nede, og tokenet optræder ikke i
klient-bundlet.

## Feature B — Beholdning (madplan-ejet)

Ingen ny infrastruktur. Rækkefølge på LXC 103:

1. **madplan-api:** `cd /opt/nova-madplan && git pull && docker compose down && docker compose up -d --build`
   (`inventory_items`-tabellen oprettes automatisk ved opstart). NB: madplans
   forslags-motor bruger ikke længere brains `/api/internal/inventory` —
   `INTERNAL_API_TOKEN` i madplans `.env` er nu ubrugt (kan blive stående).
2. **Frontend:** `npm ci && npm run build && npx wrangler deploy` (fra repo-roden
   på PC'en). Nyt menupunkt "Beholdning" + `/import`.
3. **brain:** `cd /opt/lifehub && git pull && docker compose down && docker compose up -d --build`
   (beholdnings-poll + dashboard-blok).
4. **Dashboard-PWA:** `cd /opt/lifehub/dashboard && npm ci && npm run build` og
   genudgiv `dist/` som hidtil.

Verifikation (§4.4): paste en nemlig-ordre → varer i beholdningen; tryk
Genberegn under Forslag → `inventory_hash` i svaret fra
`GET /api/suggestions/current` har skiftet; dashboard-kortet "Beholdning"
dukker op; stop madplan-api → kortet viser "gemt kopi".
