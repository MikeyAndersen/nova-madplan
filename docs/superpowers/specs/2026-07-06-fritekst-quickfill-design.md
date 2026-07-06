# Design — Fri-tekst-quickfill af ugeplan (Feature A)

> **Status:** godkendt design (brainstorm), afventer implementeringsplan.
> **Kontekst:** Fase 7-frontenden er live (`madplan.nova-tech.dk`, Astro SSR + BFF
> mod FastAPI-backend). Denne feature genindfører fri-tekst-udfyldning af en uge,
> som fandtes i den gamle D1-version (commit `47b8297` "Add quick-fill: paste a
> whole week as 'Dag: mad' lines") og blev bevidst droppet i Fase 7 (§3.4).
> Sprog: dokumentation dansk, kode/API/JSON engelsk. **Ingen backend-ændring.**

---

## 0. Beslutninger truffet under brainstorm (låst)

1. **Tekst → dag via preview.** Paste parses og matches mod aktive retter; en
   **preview-skærm** viser resultatet pr. dag, og brugeren bekræfter/justerer før
   noget gemmes. Ingen overraskelser i ret-kataloget.
2. **"+AI forslag" viser forslag til godkendelse** (ikke auto-accept): genberegner
   og sender brugeren til det eksisterende `/forslag`, hvor tomme dage kan
   accepteres pr. dag eller via "accepter alle tomme".
3. **Placering:** knap på `/madplan`, rammer den uge der navigeres til (uge-pilene).
4. **Konflikt-håndtering:** `cooked`-dage røres aldrig; `planned`-dage vises som
   konflikt hvor brugeren vælger overskriv/behold.
5. **Ingen backend-ændring** — alt bygger på eksisterende endpoints.

---

## 1. Flow

1. På `/madplan` (den viste uge): knap **"Indsæt uge fra tekst"** åbner et paste-felt.
2. Bruger skriver linjer, fx:
   ```
   Mandag: Kødsovs
   Tirsdag: grill+rester
   ```
   Uden dagnavne fordeles linjerne i rækkefølge mandag→søndag.
3. Submit → BFF **parser** teksten og **matcher** hver titel mod aktive retter →
   returnerer et **preview** (`PreviewDay[]`).
4. **Preview-skærm**, pr. dag (dato + ugedag):
   - ✅ **Match** — viser den eksisterende ret der blev fundet (`dish_id`).
   - ✨ **Ny** — vælg pr. linje: *opret som ret* / *behold som note* / *vælg
     eksisterende ret* (DishPicker-mønster).
   - ⚠️ **Konflikt** (dagen er allerede `planned`) — viser nuværende ret; vælg
     *overskriv* / *behold*.
   - 🔒 **Cooked** — vises men låst; røres aldrig.
   - ⬜ **Tom** (ingen linje for dagen) — markeres "fyldes evt. af +AI forslag".
5. **Bekræft** → BFF anvender beslutningerne: opret evt. nye retter
   (`POST /api/dishes`) → `PUT /api/weekplan/day` pr. dag (`dish_id` eller `note`,
   status `planned`). Best-effort pr. dag; returnerer pr-dag-resultat.
6. Efter anvendelse: knap **"+AI forslag"** → BFF kalder
   `POST /api/suggestions/refresh` og redirecter til `/forslag`. Der viser den
   eksisterende skærm forslag for de tomme dage; bruger accepterer pr. dag eller
   "accepter alle tomme" (springer `planned`/`cooked` over — menneske-vinder).

---

## 2. Komponenter

| Enhed | Ansvar | Afhænger af |
|---|---|---|
| `src/lib/weekplan.ts` | **Gendannes fra `47b8297`.** Ren parser `parseWeekPlan(raw): WeekPlanEntry[]` — dag-map (mandag…søndag + forkortelser) + rækkefølge-fallback; sidste linje pr. dag vinder; kolon-linjer med ukendt dagnavn ignoreres. Uændret logik. | — |
| `src/lib/weekplan-match.ts` (ny) | Ren funktion: normalisér titel + retnavn (lowercase, trim, ø/å/æ-fold) → find match blandt aktive retter. Returnerer `dish_id` eller `null`. | `Dish`-typen |
| `src/lib/weekplan-preview.ts` (ny) | Ren funktion: `(parsed, activeDishes, currentWeek) → PreviewDay[]` — sammensætter match/ny/konflikt/cooked/tom pr. dag. | ovenstående |
| BFF `POST /api/weekplan/preview` | Session-gated. `{weekStart, raw}` → henter aktive retter + uge → `PreviewDay[]`. Vedhæfter Bearer server-side. | `api.ts` |
| BFF `POST /api/weekplan/apply` | Session-gated. `{weekStart, decisions[]}` → opret nye retter, PUT dage (best-effort) → opdateret uge + pr-dag-status. | `api.ts` |
| Paste-panel + preview-UI (`/madplan`) | Textarea → preview → bekræft. "+AI forslag"-knap. Genbruger design-system + DishPicker. | BFF-ruter |

"+AI forslag" tilføjer **ingen** ny backend: den genbruger eksisterende
`POST /api/suggestions/refresh` + redirect til `/forslag`.

### Datatyper (frontend)
```ts
interface WeekPlanEntry { weekday: number; title: string; } // 1=man … 7=søn
type PreviewKind = 'match' | 'new' | 'conflict' | 'cooked' | 'empty';
interface PreviewDay {
  date: string;            // ISO
  weekday: number;
  parsedTitle?: string;
  kind: PreviewKind;
  matchedDishId?: number;  // ved 'match'
  matchedDishName?: string;
  currentDishName?: string; // ved 'conflict'
}
interface ApplyDecision {
  date: string;
  action: 'create_dish' | 'use_dish' | 'note' | 'skip';
  dishId?: number;   // use_dish
  title?: string;    // create_dish / note
}
```

---

## 3. Fejl & edge cases

- Tomme/ugyldige linjer og kolon-linjer med ukendt dagnavn ignoreres af parseren.
- Mere end 7 brugbare linjer i fallback: kun de første 7 (man→søn) bruges.
- Backend nede → venlig fejlbanner, aldrig hvid side. **Apply er best-effort pr.
  dag**: hvis en PUT/POST fejler, fortsættes de øvrige, og resultatet rapporterer
  hvilke dage der blev gemt og hvilke fejlede.
- Apply er idempotent (PUT pr. dag) — kan køres igen uden skade.
- `LIFEHUB_API_TOKEN` når aldrig klienten (BFF-mønster, uændret).

---

## 4. Test (vitest, TDD på ren logik)

- **Parser** (`weekplan.ts`): gendan/genopret tests fra git — dag-navne,
  forkortelser, rækkefølge-fallback, sidste-linje-vinder, ignorér ukendt kolon-dag.
- **Match** (`weekplan-match.ts`): normalisering (ø/å/æ, case, whitespace),
  match / intet match.
- **Preview** (`weekplan-preview.ts`): parsed + retter + uge → `PreviewDay[]`,
  inkl. konflikt (planned), cooked-lås, tomme dage, ny-ret.
- BFF-ruter dækkes via de rene funktioner + let integrationsdæk (mock fetch).

---

## 5. Afgrænsning (YAGNI)

- Ingen backend-ændring, ingen ny tabel, ingen batch-endpoint i backenden (apply
  looper eksisterende `PUT /api/weekplan/day`).
- "+AI forslag" er en genvej til eksisterende `/forslag`-flow, ikke ny logik.
- Ingen historik/undo ud over at PUT er idempotent og dage kan redigeres normalt.
