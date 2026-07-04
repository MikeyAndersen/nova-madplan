# nova-madplan

Selvstændig **madplan-service** til husstanden: retter (katalog), ugeplaner med
historik og — senere — forslag. Del af LifeHub-økosystemet, men eget repo og egen
stack. Dansk, mobil-først.

> **Kontrakt:** Al integration mod LifeHub er styret af
> [`lifehub/docs/INTEGRATION_SPEC.md`](../lifehub/docs/INTEGRATION_SPEC.md).
> Ansvarsfordeling (§A2/§A3): madplan ejer retter/ugeplaner/historik/forslag;
> lager ejes af LifeHub/Vikunja og hentes via brain — madplan taler aldrig direkte
> med Vikunja.

## Stack

- **FastAPI + SQLite** (`/data/madplan.db`), kørt som container på LXC 103.
- Deployes på det delte, eksterne Docker-netværk **`lifehub_net`** (service-discovery
  via container-navn; internt `http://madplan-api:8000`).
- Service-til-service auth via **Bearer-tokens i `.env`** (`LIFEHUB_API_TOKEN`) —
  ingen hardcoded secrets, API'et fejler lukket uden token (§0.4).
- Tests: **pytest**.

Astro/Cloudflare Workers-stacken er udgået (juli 2026) — erstattet af denne service
som del af nova-madplan ↔ LifeHub-integrationen. Gammel D1-data er migreret ind via
`api/scripts/migrate_d1.py`.

## API (Fase 1)

| Metode | Path | Auth | Beskrivelse |
|--------|------|------|-------------|
| GET | `/healthz` | ingen | Liveness |
| GET | `/api/weekplan/current` | Bearer | Indeværende uges plan (INTEGRATION_SPEC §2.2) |
| GET | `/api/weekplan?start=YYYY-MM-DD` | Bearer | Vilkårlig uge |
| PUT | `/api/weekplan/day` | Bearer | Sæt/ryd en dag; `cooked` ⇄ historik ⇄ `last_made` vedligeholdes |
| GET/POST/PATCH/DELETE | `/api/dishes` | Bearer | Ret-katalog (CRUD, soft delete) |

Forslags-motor, brain-inventory-integration og 32b-drain kommer i senere faser
(§7 Fase 4–5).

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
