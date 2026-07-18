# nova-madplan

Selvstændig **madplan-service** til husstanden: retter (katalog), ugeplaner med
historik og — senere — forslag. Del af LifeHub-økosystemet, men eget repo og egen
stack. Dansk, mobil-først.

> **Kontrakt:** Al integration mod LifeHub er styret af
> [`lifehub/docs/INTEGRATION_SPEC.md`](../lifehub/docs/INTEGRATION_SPEC.md).
> Ansvarsfordeling: madplan ejer retter/ugeplaner/historik/forslag **og beholdning**.
> Beholdningen er **madplan-ejet** siden Feature B (2026-07-16, egen
> `inventory_items`-tabel); forslags-motoren læser sin egen tabel og bruger ikke
> længere brains `/api/internal/inventory`. brain poller nu madplans beholdning til
> dashboardet (retningen er vendt om). madplan taler fortsat aldrig direkte med Vikunja.
>
> Se [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) for fuldt projektoverblik.

## Stack

- **FastAPI + SQLite** (`/data/madplan.db`), kørt som container på LXC 103.
- Deployes på det delte, eksterne Docker-netværk **`lifehub_net`** (service-discovery
  via container-navn; internt `http://madplan-api:8000`).
- Service-til-service auth via **Bearer-tokens i `.env`** (`LIFEHUB_API_TOKEN`) —
  ingen hardcoded secrets, API'et fejler lukket uden token (§0.4).
- Tests: **pytest**.

Den **gamle Astro + Cloudflare D1**-stack (database i D1) er udgået (juli 2026) —
databasen er flyttet til denne FastAPI+SQLite-service, og gammel D1-data er migreret
ind via `api/scripts/migrate_d1.py`. Den **nuværende frontend** er stadig Astro på
Cloudflare Workers (Fase 7), men kører nu som BFF mod dette API i stedet for mod D1 —
se `docs/PROJECT_OVERVIEW.md`.

## API

| Metode | Path | Auth | Beskrivelse |
|--------|------|------|-------------|
| GET | `/healthz` | ingen | Liveness |
| GET | `/api/weekplan/current` | Bearer | Indeværende uges plan (INTEGRATION_SPEC §2.2) |
| GET | `/api/weekplan?start=YYYY-MM-DD` | Bearer | Vilkårlig uge |
| PUT | `/api/weekplan/day` | Bearer | Sæt/ryd en dag; `cooked` ⇄ historik ⇄ `last_made` vedligeholdes |
| GET/POST/PATCH/DELETE | `/api/dishes` | Bearer | Ret-katalog (CRUD, soft delete) |
| GET | `/api/suggestions/current` | Bearer | Ugens AI-forslag |
| POST | `/api/suggestions/refresh` | Bearer | Genberegn forslag |
| POST | `/api/suggestions/accept` | Bearer | Accepter forslag (enkeltdag eller hel uge) |
| POST | `/api/suggestions/reject` · `/reject-all` · `/reset-rejections` | Bearer | Forkast-hukommelse (Feature B) |
| GET | `/api/stats` | Bearer | Statistik: antal-lavet pr. ret + pr. måned |
| GET/POST/PATCH/DELETE | `/api/inventory` | Bearer | Beholdning (CRUD + bulk-add med merge-på-navn) |
| POST | `/api/recipes/scrape` | Bearer | Scrape URL → preview (gemmer ikke) |
| GET/POST/PATCH/DELETE | `/api/recipes` | Bearer | Opskrifter (CRUD + cachet billede) |
| GET | `/api/recipes/{id}/image` | Bearer | Cachet billede-bytes |
| POST | `/api/drain` | `MADPLAN_DRAIN_TOKEN` | 32b-agentens additive drain (§5) |

Forslags-motoren (14-dages-regel, lager-scoring, 7b-ranking + deterministisk
fallback) og 32b-drain er implementeret. Se
[`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md).

## Udvikling

Fra `api/`-mappen:

```sh
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt pytest   # Windows
# source .venv/bin/activate && pip install -r requirements.txt pytest  # Linux/mac

DATABASE_PATH=./madplan.db LIFEHUB_API_TOKEN=dev \
  ./.venv/Scripts/python -m uvicorn app.main:app --reload   # http://localhost:8000

./.venv/Scripts/python -m pytest -q                          # tests
```

Miljøvariabler: se [`.env.example`](.env.example) (§6). `DATABASE_PATH` styrer db-stien
(default `/data/madplan.db` i containeren).

## Deploy (LXC 103, manuelt)

```sh
docker network create lifehub_net          # én gang, deles med LifeHub-stacken
cd /opt/nova-madplan
cp .env.example .env && $EDITOR .env        # udfyld LIFEHUB_API_TOKEN m.fl.
docker compose up -d --build

# verifikation (§7 Fase 1 accept-kriterium):
curl -H "Authorization: Bearer $LIFEHUB_API_TOKEN" \
     http://localhost:8400/api/weekplan/current      # → gyldig §2.2-JSON, 7 dage
```

Host-porten `8400` er kun til LAN-verifikation/frontend; internt bruger brain
`http://madplan-api:8000`. `.env`-ændringer kræver `docker compose down && up -d`
(ikke `restart`).

## Migrering fra gammel D1

Engangs-migrering af den gamle Cloudflare D1-database (retter → dishes, fortid →
cooked + historik). Lager/priser migreres **ikke** (ejes nu af LifeHub/Vikunja),
men eksporteres til CSV ved siden af db'en.

```sh
npx wrangler d1 export madplan --remote --output=d1_dump.sql   # kræver wrangler-login
cd api
DATABASE_PATH=./madplan.db ./.venv/Scripts/python -m scripts.migrate_d1 --dump ../d1_dump.sql
```
