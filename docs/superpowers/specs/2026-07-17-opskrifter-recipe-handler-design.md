# Design — Opskrifter (recipe handler med scrape + cache)

> **Status:** godkendt design (brainstorm), afventer implementeringsplan.
> **Kontekst:** madplan-frontenden (Astro SSR + BFF mod FastAPI) er live på
> `madplan.nova-tech.dk`. Denne feature tilføjer et **opskrifts-katalog** hvor
> opskrifter fra nettet **scrapes og caches**, så de aldrig går tabt når sider
> ændres eller lukker. Sprog: dokumentation dansk, kode/API/JSON engelsk.
> **Ny backend-kode** (nye tabeller, scraping) — modsat Feature A.

---

## 0. Beslutninger truffet under brainstorm (låst)

1. **Cookbook-model.** Opskrifter er en selvstændig enhed med egen side
   (`/opskrifter`) — et søgbart arkiv. En **ret** kan pege på én opskrift
   (`dishes.recipe_id`, valgfri). Opskrifter eksisterer uafhængigt af om de
   nogensinde planlægges.
2. **Capture = struktureret + rå snapshot.** Ved gem parses strukturerede felter
   (titel, ingredienser, trin, tid, billede), OG der gemmes altid et **rå
   readable snapshot** af siden som sikkerhedsnet. Et gem mister aldrig siden.
3. **Billeder caches som bytes** (gemmes i backenden), så de overlever at
   kilde-sitet lukker. Serveres via BFF (token forbliver server-side).
4. **Tre input-metoder:** paste URL (auto-scrape → preview → bekræft), manuel
   indtastning (er også editoren til at rette en dårlig scrape), og paste rå
   tekst (gemmes as-is, let parset, redigerbar).
5. **Scraping sker i backenden** (Python), aldrig i Workeren.
6. **To broer til madplanen:** fra en ret kan man **vedhæfte en opskrift**; fra en
   opskrift kan man **"opret ret fra opskrift"** (ny ret præudfyldt med navn +
   ingredienser, allerede linket).

---

## 1. Datamodel

### Ny tabel `recipes`
| Felt | Type | Note |
|---|---|---|
| `id` | int PK | |
| `title` | str | |
| `source_url` | str \| null | null ved manuel |
| `ingredients` | JSON | genbruger `{name, qty, unit}` (samme som `Dish.ingredients`) |
| `steps` | JSON (list[str]) | tilberedningstrin |
| `time_min` | int \| null | samlet tid i minutter |
| `tags` | JSON (list[str]) | |
| `raw_snapshot` | text | fuld readable sidetekst — sikkerhedsnettet |
| `has_image` | bool | om der findes cachet billede |
| `image_mime` | str \| null | fx `image/jpeg` |
| `created_at`, `updated_at` | str (ISO) | |

### Ny tabel `recipe_images`
Billed-bytes holdes adskilt fra `recipes` (så list-queries ikke trækker BLOBs):
`recipe_id` PK/FK → `recipes.id`, `bytes` BLOB, `mime` str. Gemmes i samme
SQLite-fil ⇒ backup forbliver **én fil**.

### Ændring af `dishes`
Ny kolonne **`recipe_id` int \| null** (valgfri FK → `recipes.id`). Tilføjes
til `Dish`/`DishUpdate`-modellerne og `/api/dishes`-CRUD. `ON DELETE SET NULL`
(slettes en opskrift, mister retten bare linket).

### Frontend-typer (`src/lib/api.types.ts`)
```ts
interface Recipe {
  id: number;
  title: string;
  source_url: string | null;
  ingredients: Ingredient[];        // eksisterende type
  steps: string[];
  time_min: number | null;
  tags: string[];
  raw_snapshot: string;
  has_image: boolean;
  created_at: string;
  updated_at: string;
}
interface RecipeInput {              // manuel/bekræftet scrape
  title: string;
  source_url?: string | null;
  ingredients?: Ingredient[];
  steps?: string[];
  time_min?: number | null;
  tags?: string[];
  raw_snapshot?: string;
}
interface ScrapePreview {           // svar fra /scrape, endnu ikke gemt
  parsed: RecipeInput;              // bedste strukturerede bud (felter kan være tomme)
  image_url: string | null;        // kandidat-billede (hentes ved gem)
  ok: boolean;                     // om strukturel parse lykkedes
  warning?: string;                // fx "ingen strukturerede data — udfyld selv"
}
```

---

## 2. Backend

### Endpoints (alle Bearer-gated som resten af API'et)
| Metode | Path | Beskrivelse |
|---|---|---|
| POST | `/api/recipes/scrape` | `{url}` → henter + parser → `ScrapePreview` (**gemmer ikke**) |
| GET | `/api/recipes?q=` | Liste (uden BLOB); `q` søger i titel + ingrediensnavne |
| POST | `/api/recipes` | Opret (`RecipeInput` + valgfri `image_url` hentes/caches) → `Recipe` |
| GET | `/api/recipes/{id}` | Detalje |
| PATCH | `/api/recipes/{id}` | Redigér felter (editoren) |
| DELETE | `/api/recipes/{id}` | Slet (retter får `recipe_id=NULL`) |
| GET | `/api/recipes/{id}/image` | Billed-bytes (`Content-Type` = `image_mime`) |

Ret-link genbruger eksisterende `PATCH /api/dishes/{id}` udvidet med `recipe_id`.

### Scraping-motor (nyt modul `api/app/recipes.py` + `scrape.py`)
1. **Hent** siden med `httpx` (eksisterende dep), timeout + venlig User-Agent.
2. **Strukturér:** primært et opskrifts-bibliotek (fx `recipe-scrapers`), med
   generisk **schema.org/Recipe JSON-LD**-fallback. Fylder `title, ingredients,
   steps, time_min, image_url`.
3. **Rå snapshot:** en readability/extraction-lib (fx `trafilatura`) → ren
   sidetekst. **Kører altid**, uafhængigt af om (2) lykkedes.
4. **Fail-soft:** lykkes (2) ikke, returneres `ok:false` + `warning`, med
   `raw_snapshot` udfyldt og tomme strukturerede felter — brugeren udfylder selv.
   Et gem må **aldrig** fejle pga. mislykket strukturel parse.
5. **Billede:** ved `POST /api/recipes` hentes `image_url` (hvis givet) én gang,
   bytes + mime gemmes i `recipe_images`. Fejl her er ikke-fatal (`has_image=false`).

Nye Python-deps tilføjes `api/requirements.txt` (scraping + extraction). Backend
er containeriseret, så det er uproblematisk.

---

## 3. Frontend

### Sider
- **`/opskrifter`** — kataloget: søgefelt + kort (thumbnail via
  `/api/recipes/{id}/image`, titel, tid, tags). Knap **"Tilføj opskrift"** med tre
  faner: **URL** / **Manuel** / **Indsæt tekst**.
  - URL-fanen: paste → `POST /api/recipes/scrape` → **preview** (genbruger
    app'ens preview-then-confirm-mønster fra quickfill/import) → redigér → gem.
- **`/opskrifter/[id]`** — detalje: ren struktureret visning at lave mad efter;
  **"Vis original"**-toggle for `raw_snapshot`; **Redigér** (samme form som
  manuel); **Vedhæft til ret** / **Opret ret fra opskrift**; kildelink.
- **`/madplan` + ret-visning:** har en planlagt ret en linket opskrift, vises et
  link direkte til `/opskrifter/[id]`.
- **Nav:** nyt punkt **"Opskrifter"** i `src/components/Nav.astro`.

### BFF (`src/pages/api/recipes/`)
Server-side proxy for alle recipe-kald; vedhæfter Bearer. Billed-ruten streamer
bytes fra backendens `/api/recipes/{id}/image`, så tokenet aldrig når klienten.
`src/lib/api.ts` udvides med recipe-metoder (`scrapeRecipe`, `listRecipes`,
`createRecipe`, `getRecipe`, `updateRecipe`, `deleteRecipe`).

---

## 4. Fejl & edge cases

- **Site nede / timeout ved scrape:** venlig fejl i preview; brugeren kan skifte
  til Manuel og gemme alligevel. Aldrig hvid side.
- **Ingen strukturerede data:** `ok:false` + snapshot udfyldt → manuel udfyldning.
- **Billed-hentning fejler:** opskriften gemmes uden billede (`has_image=false`).
- **Slettet opskrift:** retter der pegede på den får `recipe_id=NULL` (ret-planen
  brydes ikke).
- **Store snapshots:** gemmes as-is i text-kolonne; billeder i separat tabel så
  list-queries er lette.
- **Token:** `LIFEHUB_API_TOKEN` når aldrig klienten (BFF-mønster, uændret).

---

## 5. Test

- **Backend (pytest):** scrape-parser mod gemte HTML-fixtures (schema.org-side,
  side uden strukturerede data → fail-soft, side med billede); recipe-CRUD;
  `recipe_id`-link + `ON DELETE SET NULL`; billed-endpointet returnerer korrekt
  `Content-Type`. Netværk mockes (ingen rigtige fetches i tests).
- **Frontend (vitest):** api-klientens recipe-metoder; preview→decisions-mapping;
  søgning/filtrering af liste.

---

## 6. Afgrænsning (YAGNI — v1)

- **Ingen** portions-skalering af ingredienser.
- **Ingen** auto-tilføjelse af opskrift-ingredienser til beholdning/indkøb —
  stærk fremtidig synergi med eksisterende inventory + nemlig-parser, men uden
  for v1.
- Ingen ratings, ingen deling, ingen multi-bruger.
- Én opskrift pr. ret (ikke mange-til-mange).
