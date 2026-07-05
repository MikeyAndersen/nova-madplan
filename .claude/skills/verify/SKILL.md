---
name: verify
description: Kør madplan-frontenden (Astro SSR) mod en lokal FastAPI-backend og driv flows med curl
---

# Verify — madplan frontend + backend lokalt

## Backend (FastAPI, port 8400)

```bash
python -m venv <scratch>/venv && <scratch>/venv/Scripts/pip install -r api/requirements.txt
cd api && DATABASE_PATH=<scratch>/madplan-verify.db LIFEHUB_API_TOKEN=dev SUGGEST_AUTO=false \
  <scratch>/venv/Scripts/python -m uvicorn app.main:app --port 8400 --host 127.0.0.1
```

Brug ALDRIG `api/madplan.db` (rigtige data) — sæt altid `DATABASE_PATH` til en scratch-fil.
`SUGGEST_AUTO=false` slår baggrunds-triggere fra. Forslags-refresh virker alligevel
(deterministisk fallback når Ollama/brain er utilgængelige).

## Frontend (Astro dev, port 4321)

```bash
npx astro dev --port 4321 --host 127.0.0.1
```

`astro dev` læser `vars` fra `wrangler.jsonc` (MADPLAN_API_BASE=http://localhost:8400,
LIFEHUB_API_TOKEN=dev, SITE_PASSWORD=dev) via @astrojs/cloudflare platform proxy.

## Drive med curl

- **CSRF:** Alle POSTs kræver `-H "Origin: http://127.0.0.1:4321"` — ellers 403 (Astros checkOrigin).
- **Login:** `curl -X POST -H "Origin: ..." -d "password=dev" -c cookies.txt http://127.0.0.1:4321/login` → 302 + `madplan_session`-cookie. Brug `-b cookies.txt` derefter.
- **Dag-form:** POST `/api/day` med `date, week_start, status(planned|cooked|empty), dish_id|new_dish_name, note` → 302 tilbage til `/madplan?start=...` (`&error=1` ved fejl).
- **Retter:** POST `/api/dishes` med `action=create|update|toggle|recurring|delete`.
- **Forslag:** POST `/api/suggestions/refresh` (202), GET `/api/suggestions/poll` (`{updated_at}`), POST `/api/suggestions/accept` (`date+dish_id` eller `all=1&week_start=`).

## Gotchas

- Backend-svar på ugyldig `?start=` er 422 → siden viser banner "Kunne ikke hente madplanen (422)".
- Fejlbannere ved backend nede er et accept-kriterium (§3.5.6) — test ved at stoppe uvicorn.
- Token-lækage tjekkes KUN i `dist/client` (`dist/server` er Worker-kode og må referere env).
