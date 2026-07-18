# Design — Madplan-UX: smart ret-vælger, forkast-hukommelse & statistik

> **Status:** godkendt design (brainstorm), afventer implementeringsplaner.
> **Kontekst:** Opskrifter-featuren er live. Denne epic forbedrer selve
> planlægnings-oplevelsen i tre dele, der bygges i rækkefølge **A → B → D**.
> Sprog: doku dansk, kode/API/JSON engelsk. Ny backend- og frontend-kode.

---

## 0. Låste beslutninger (brainstorm)

**A — Smart ret-vælger** (`/madplan` "+ Tilføj ret"):
- Erstat native `<datalist>` i `DishPicker.astro` med et lille **custom autocomplete**
  (nødvendigt for kilde-badges + tastatur-nav).
- **Én samlet liste, dedupliceret pr. ret, med kilde-badges.** En ret får badge
  `📖 opskrift` (hvis `recipe_id` sat) og/eller `✨ AI` (hvis den er i det aktuelle
  forslags-sæt). Opskrifter **uden** linket ret vises som egne `📖 opskrift`-punkter.
- **AI-forslag: alle aktuelle forslag som `✨ AI`-punkter i enhver dags vælger.**
- **Rangering:** tekst-match først, derefter flest-lavede (frekvens, fra D),
  med et lille løft til `✨ AI`.
- **Tastatur:** skriv for at filtrere (accent/case-ufølsomt); ArrowDown/Up flytter
  markering; Enter vælger; Escape lukker; klik virker. Eksakt tekst-match
  præ-markeres (Enter/pil-ned-Enter).
- **Valg → handling:** ret → planlæg den; opskrift-uden-ret → opret/genbrug dens
  ret, planlæg; fri tekst → ny ret (som i dag).

**B — Forkast-hukommelse** (`/forslag`):
- **Begge** forkast-veje: per-kort **👎 Forkast** + **"Forkast alle og genberegn"**.
- Forkastede retter huskes **pr. uge**, overlever Genberegn, ekskluderes fra
  kandidat-pulje OG nævnes i LLM-prompten. Ryddes hvis retten senere planlægges,
  eller via nulstil. **Blødgøres** hvis eksklusion ville tømme for mange dage.

**D — Statistik** (`/statistik`):
- **Tabel + lette grafer.** Rangeret tabel (ret · antal gange lavet · sidst lavet,
  flest øverst) + total, plus en lille søjlegraf over top-retter og måltider-pr-måned.
- Antal-lavet kommer fra `history`-tabellen og **deler endpoint med A's rangering**.

---

## 1. Feature A — Smart ret-vælger

### Datakilder (server-side på `/madplan`)
`madplan/index.astro` henter nu også: `listRecipes()`, `getSuggestions()`, og
**ret-frekvenser** (`GET /api/stats` → `dishes[].times_made`). Sendes til
`DishPicker` sammen med de eksisterende `dishes`.

### Sammensætning af optioner (ren funktion `buildPickerOptions`)
Ny `src/lib/picker-options.ts`:
```ts
type PickerKind = 'dish' | 'recipe';
interface PickerOption {
  label: string;            // vist navn
  kind: PickerKind;         // 'dish' → dish_id; 'recipe' → recipe_id (uden ret)
  dishId?: number;
  recipeId?: number;
  badges: ('ret' | 'opskrift' | 'ai')[];
  timesMade: number;        // til rangering (0 for opskrift-uden-ret)
}
function buildPickerOptions(
  dishes: Dish[], recipes: Recipe[], suggestionDishIds: Set<number>,
  counts: Map<number, number>
): PickerOption[]
```
Regler: hver aktiv ret = ét punkt (`kind:'dish'`, badge `ret`; +`opskrift` hvis
`recipe_id`; +`ai` hvis i `suggestionDishIds`). Hver opskrift **uden** en ret der
peger på den (`recipe.id` ikke i `{d.recipe_id}`) = ét punkt (`kind:'recipe'`,
badge `opskrift`). Rangering: `timesMade` desc, `ai` giver +bonus, alfabetisk tie-break.

### Widget (`DishPicker.astro`, custom autocomplete)
- Tekst-input + skjult liste (`role=listbox`), absolut placeret.
- Filtrering: normalisér (lowercase, ø/å/æ-fold) → substring-match på `label`.
- Rækkefølge: matches i `buildPickerOptions`-orden; til sidst altid
  **"+ Opret '<tekst>' som ny ret"** når teksten ikke er et eksakt match.
- Tastatur: ArrowDown/Up (wrap), Enter (vælg markering), Escape (luk), Tab (luk).
- Badges vises som små pills pr. række; farvekodet (ret neutral, opskrift, ai-accent).
- Ved valg sættes skjulte felter i dags-formen: `dish_id` | `recipe_id` | `new_dish_name`
  (præcis ét). Formen POSTer som i dag til `/api/day`.

### BFF `/api/day` (udvid)
Accepterer nu valgfrit **`recipe_id`**. Hvis sat og intet `dish_id`: opret en ret
fra opskriften (`createDish({name, ingredients})` + link `recipe_id`) → brug dens
`id`. (Genbruger `make-dish`-logikken; kaldes kun for opskrifter der endnu ikke
har en ret.) Ellers uændret (`dish_id` / `new_dish_name`).

### Test
- vitest: `buildPickerOptions` (dedup, badges, rangering, opskrift-uden-ret);
  widget-filtrering/normalisering (ren funktion udtrukket).
- BFF-day med `recipe_id` (mock api).

---

## 2. Feature B — Forkast-hukommelse

### Data
Ny tabel:
```sql
CREATE TABLE IF NOT EXISTS suggestion_rejections (
    week_start TEXT NOT NULL,
    dish_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (week_start, dish_id)
);
```

### Backend
- `suggest.rejected_ids(conn, week_start) -> set[int]`.
- **`candidate_pool` udvides** med `exclude: set[int]`: fjern forkastede; **men hvis
  puljen derved falder under 7 (antal dage), gen-inkludér forkastede** (ældst-forkastet
  først) indtil ≥7 — en tom dag er værre end en gentagelse.
- **`_build_prompt`**: tilføj linje `UNDGÅ disse retter (nyligt forkastet): [navne]`.
- `generate()`/`drain_once()` læser `rejected_ids` for ugen og sender til
  `candidate_pool` + prompt.
- **Ryd ved accept:** når en ret planlægges for en dato i næste uge (accept-endpoint),
  slet dens rejection-række for den uge (menneske ombestemte sig).

### Endpoints (alle Bearer)
| Metode | Path | Beskrivelse |
|---|---|---|
| POST | `/api/suggestions/reject` | `{dish_id}` → forkast for næste uge (upsert) |
| POST | `/api/suggestions/reject-all` | forkast alle dish_id i aktuelt sæt → trig `generate(force=True)` |
| POST | `/api/suggestions/reset-rejections` | ryd ugens forkastede |

`/refresh` er uændret (kalder `generate(True)`), men respekterer nu forkastede.

### Frontend `/forslag`
- Per-kort **👎 Forkast** → `POST /api/suggestions/reject` (BFF) → reload.
- **"Forkast alle og genberegn"** → `POST /api/suggestions/reject-all` → poll til
  `updated_at` skifter → reload (genbrug eksisterende poll-mønster).
- Lille **"Nulstil forkastede"** når der er nogen.

### Test
- pytest: `candidate_pool` med `exclude` (normal + blødgør-under-7); `rejected_ids`;
  prompt indeholder forkastede navne; accept rydder rejection; reject/reject-all/reset
  endpoints; `generate` udelader forkastet ret.

---

## 3. Feature D — Statistik

### Backend `GET /api/stats` (Bearer)
Fra `history` (én række pr. cooked dato):
```json
{
  "total_cooked": 128,
  "dishes": [{"dish_id": 3, "name": "Kødsovs", "times_made": 12, "last_made": "2026-07-10"}],
  "per_month": [{"month": "2026-07", "count": 9}]
}
```
`dishes` sorteret `times_made` desc. Deles med A (rangering bruger `times_made`).

### Frontend `/statistik` (ny side + nav-punkt)
- Rangeret **tabel:** ret · antal gange · sidst lavet.
- **Lette grafer** (inline SVG/CSS, ingen eksterne libs pga. Worker-CSP): søjlegraf
  top-N retter + måltider-pr-måned. Brug `dataviz`-skill til palette/formgivning.
- Total-tal øverst.

### Test
- pytest: `/api/stats` tæller korrekt fra `history` (fixtures med cooked-dage),
  sortering, `per_month`-gruppering.
- vitest: evt. ren hjælpefunktion til søjle-skalering.

---

## 4. Tværgående

- **`GET /api/stats` deles** af A (frekvens-rangering) og D (siden). Ét endpoint.
- Ingen ændring af `Dish`-kontrakten (§2.1) i denne epic.
- `recipe_id` på `Day` findes allerede (bruges til 📖-link) — genbruges ikke her.

## 5. Afgrænsning (YAGNI)

- Ingen per-bruger-stats, ingen eksport, ingen redigerbar historik.
- Forkast-hukommelse er pr. uge, ikke en global "kan ikke lide"-liste.
- Ingen drag-and-drop i vælgeren; kun tastatur + klik.
- Grafer er statiske (ingen interaktiv filtrering ud over det byggede).
