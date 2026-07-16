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

`wrangler.jsonc`'s `vars` peger på **produktions**-API'en. Lokalt skal du derfor oprette
`.dev.vars` (gitignoreret) i repo-roden, ellers rammer `astro dev` prod bag Cloudflare
Access og alle POSTs redirecter til `?error=1`:

```
MADPLAN_API_BASE=http://127.0.0.1:8400
LIFEHUB_API_TOKEN=dev
```

Kvittér på at `astro dev` skriver `Using secrets defined in .dev.vars` ved opstart.
Hvis port 4321 er optaget, tager Astro den næste ledige (4322…) — brug den port i både
URL og `Origin`-header.

## Drive med curl

- **CSRF:** Alle POSTs kræver `-H "Origin: http://127.0.0.1:4321"` — ellers 403 (Astros checkOrigin).
- **Login:** findes ikke længere — adgang gates af Cloudflare Access ved edge (commit `4bf9e01`). Ingen cookie-håndtering nødvendig.
- **Dag-form:** POST `/api/day` med `date, week_start, status(planned|cooked|empty), dish_id|new_dish_name, note` → 302 tilbage til `/madplan?start=...` (`&error=1` ved fejl).
- **Retter:** POST `/api/dishes` med `action=create|update|toggle|recurring|delete`.
- **Forslag:** POST `/api/suggestions/refresh` (202), GET `/api/suggestions/poll` (`{updated_at}`), POST `/api/suggestions/accept` (`date+dish_id` eller `all=1&week_start=`).
- **Beholdning:** POST `/api/inventory` med `action=add|update|consume|delete`. `consume` sender varens **nuværende** `quantity` + `id`; BFF'en trækker 1 fra og sletter varen når resultatet rammer 0.
- **Import:** POST rå tekst som `raw` til `/import` → bekræftelses-skærm (200). Bekræft ved at POSTe `item_count` + pr. vare `include=<i>`, `name_<i>`, `quantity_<i>`, `unit_<i>`, `location_<i>`, `merge_<i>` til `/api/import` → 302 `/import?added=&merged=&skipped=`.

## Gotchas

- Backend-svar på ugyldig `?start=` er 422 → siden viser banner "Kunne ikke hente madplanen (422)".
- Fejlbannere ved backend nede er et accept-kriterium (§3.5.6) — test ved at stoppe uvicorn.
- Token-lækage tjekkes KUN i `dist/client` (`dist/server` er Worker-kode og må referere env).
- Nemlig-testdata: opfind ALDRIG selv linje-strukturen — parseren kræver enhed + kr.-linjer og
  returnerer ellers tavst 0 varer. Kopiér `FORMAT_A`/`FORMAT_B` verbatim fra
  `tests/nemlig/parser.test.ts` (autoritativ). Tjek `item_count` i bekræftelses-HTML'en, ikke
  varenavne — `<textarea>` ekkoer din rå input og giver falske grep-hits.
