# Madplan & Beholdning

En lille, lukket web-app til én husstand: ugentlige **madplaner** med historik og en
**beholdning** (køleskab/fryser/skab/øvrigt) der kan fyldes via import af en nemlig.com-ordre.
Dansk, mobil-først, minimalistisk.

## Stack

- **Astro 6** (SSR, `output: 'server'`) + **`@astrojs/cloudflare`** adapter (Cloudflare **Workers** med statiske assets).
- **Cloudflare D1** (SQLite), binding `DB`.
- Adgang: **ét delt password** via env `SITE_PASSWORD` → signeret session-cookie (middleware-gate).
- Tests: **Vitest** (auth, datoer, lokationer, nemlig-parser).

> Bemærk: Astro-adapteren targeter i dag Cloudflare **Workers** (ikke Pages). Custom domain og
> D1 fungerer identisk. Deploy sker via Wrangler — ikke SFTP/One.com.

## Ruter

| Rute | Indhold |
|---|---|
| `/` | Dashboard: denne uges madplan + beholdningsoverblik. |
| `/madplan` | Nuværende + kommende uger; redigér dage, markér fleks. |
| `/madplan/arkiv` | Historiske uger (skrivebeskyttet, nyeste først). |
| `/beholdning` | Køleskab · Fryser · Skab · Øvrigt; tilføj/redigér/forbrug/slet, søg+filter. |
| `/import` | Nemlig-intake: indsæt tekst → forhåndsvisning → bekræft → indsæt. |
| `/login`, `/logout` | Password-gate. |

## Udvikling

```sh
npm install
npm run dev        # localhost:4321 (D1 emuleres lokalt via Wrangler)
npm test           # kør unit-tests
npm run build      # produktionsbuild til ./dist
npx astro check    # typecheck
```

Lokalt password ligger i `.dev.vars` (`SITE_PASSWORD=mikey`) — **ikke** committet.

### Database

Skema i `migrations/0001_init.sql`. Anvend lokalt:

```sh
wrangler d1 execute madplan --local --file=./migrations/0001_init.sql
```

## Deploy (Cloudflare Workers)

Kræver at man er logget ind på den Cloudflare-konto hvor `nova-tech.dk` DNS ligger.

```sh
npm run build
wrangler deploy                                   # første deploy (opretter Worker "madplan")
wrangler d1 execute madplan --remote --file=./migrations/0001_init.sql   # migrér REMOTE D1
wrangler secret put SITE_PASSWORD                 # sæt produktions-password (= mikey)
```

Tilføj derefter custom domain `madplan.nova-tech.dk` på Worker'en (Cloudflare-dashboard →
Workers & Pages → madplan → Settings → Domains & Routes), da DNS allerede er på Cloudflare.

D1-bindingen (`DB` → `madplan`, id i `wrangler.jsonc`) gælder både lokalt og remote.
