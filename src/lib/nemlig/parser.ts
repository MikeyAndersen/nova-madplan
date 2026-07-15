import type { ParsedItem, ParsedRecipe, ParseResult } from './types';

// Best-effort nemlig-parser. Mennesket fanger fejl på bekræftelsesskærmen,
// så vi over-engineerer ikke: tvivlstilfælde havner i `unreadable`.

const KNOWN_CATEGORIES = [
  'Drikke', 'Frost', 'Grønt', 'Kolonial', 'Kød & fisk', 'Køl', 'Mejeri', 'Brød', 'Pleje',
];
const CATEGORY_BY_LOWER = new Map(KNOWN_CATEGORIES.map((c) => [c.toLowerCase(), c]));

// Enhed nær linjestart: "1 l", "500 g", "4 stk.", "1,50 kg", "2 pk.".
const UNIT_RE = /\d+(?:[.,]\d+)?\s?(?:l|ml|cl|kg|g|stk\.?|pk\.?)\b/i;

// "Cremet pasta med salsiccia 4 personer ..." → opskrift, ikke beholdning.
const RECIPE_RE = /^(.+?)\s+(\d+)\s*personer\b/i;

// Standalone pris-linje, fx "8,50 kr." (Format A).
const KR_LINE_RE = /^\s*[\d.,]+\s+kr\.?\s*$/i;

// Footer/side-chrome der altid ignoreres (§6.4) — matches på linjestart.
const IGNORE_PREFIXES = [
  'varer i alt', 'pant', 'fragt', 'pakkegebyr', 'kortgebyr', 'gavekode rabat',
  'udbetalt opsparing', 'total', 'faktura', 'faktureringsadresse', 'leveringsadresse',
  'fakturanr', 'kundenr', 'betalingsform', 'forfaldsdato', 'leveringsform',
  'leveringsdato', 'varenavn', 'fleksibel levering',
];

function categoryOf(line: string): string | undefined {
  return CATEGORY_BY_LOWER.get(line.trim().toLowerCase());
}

function isIgnored(line: string): boolean {
  const t = line.trim();
  if (!t) return true;
  if (/^side\s+\d+\s+af\s+\d+/i.test(t)) return true;
  const lower = t.toLowerCase();
  return IGNORE_PREFIXES.some((p) => lower.startsWith(p));
}

function matchRecipe(line: string): ParsedRecipe | null {
  const m = line.trim().match(RECIPE_RE);
  if (!m) return null;
  return { name: m[1].trim(), persons: parseInt(m[2], 10) };
}

/** Parse "19,96 kr." / "888,48" → 19.96 / 888.48 (dansk: komma=decimal, punktum=tusind). */
function krNum(s: string): number {
  const cleaned = s.replace(/kr\.?/i, '').trim().replace(/\./g, '').replace(',', '.');
  return parseFloat(cleaned);
}

function isNumericToken(s: string): boolean {
  return /^[\d.,]+$/.test(s);
}

function normalizeUnit(s: string): string {
  return s.replace(/\s+/g, ' ').trim();
}

/** Map fortløbende kr-beløb: sidste=total, første=stk, midterste (ved 3)=rabat. */
function mapKr(krs: number[]): Pick<ParsedItem, 'unitPrice' | 'discount' | 'total'> {
  if (krs.length === 0) return {};
  return {
    unitPrice: krs[0],
    discount: krs.length >= 3 ? krs[1] : undefined,
    total: krs[krs.length - 1],
  };
}

function isFormatA(lines: string[]): boolean {
  // Format A har standalone "X kr."-linjer; Format B har alt på én linje.
  return lines.some((l) => KR_LINE_RE.test(l));
}

function parseFormatA(lines: string[]): ParseResult {
  const items: ParsedItem[] = [];
  const recipes: ParsedRecipe[] = [];
  const unreadable: string[] = [];

  // Spring indledende header-blok over indtil første kendte kategori.
  let i = lines.findIndex((l) => categoryOf(l) !== undefined);
  if (i < 0) i = 0;

  let current = '';
  while (i < lines.length) {
    const line = lines[i];

    const cat = categoryOf(line);
    if (cat) { current = cat; i++; continue; }
    if (isIgnored(line)) { i++; continue; }

    const unitLine = lines[i + 1] ?? '';

    // Opskrift: "<navn>" efterfulgt af "<n> personer".
    const recM = unitLine.match(/(\d+)\s*personer/i);
    if (recM) {
      recipes.push({ name: line.trim(), persons: parseInt(recM[1], 10) });
      i += 2;
      while (i < lines.length && (KR_LINE_RE.test(lines[i]) || /^\s*[\d.,]+\s*$/.test(lines[i]))) i++;
      continue;
    }

    const qtyLine = (lines[i + 2] ?? '').trim();
    if (!/^\d+$/.test(qtyLine)) {
      unreadable.push(line);
      i++;
      continue;
    }

    const quantity = parseInt(qtyLine, 10);
    let j = i + 3;
    const krs: number[] = [];
    while (j < lines.length && KR_LINE_RE.test(lines[j])) {
      krs.push(krNum(lines[j]));
      j++;
    }

    items.push({
      name: line.trim(),
      category: current,
      unit: normalizeUnit(unitLine),
      quantity,
      ...mapKr(krs),
    });
    i = j;
  }

  return { items, recipes, unreadable };
}

function parseFormatB(lines: string[]): ParseResult {
  const items: ParsedItem[] = [];
  const recipes: ParsedRecipe[] = [];
  const unreadable: string[] = [];

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (isIgnored(line)) continue;

    const rec = matchRecipe(line);
    if (rec) { recipes.push(rec); continue; }

    const m = UNIT_RE.exec(line);
    if (!m || m.index === 0) { unreadable.push(line); continue; }

    const name = line.slice(0, m.index).trim();
    const rest = line.slice(m.index + m[0].length).trim();
    const nums = rest.split(/\s+/).filter(Boolean);

    if (nums.length < 2 || !nums.every(isNumericToken)) {
      unreadable.push(line);
      continue;
    }

    const n = nums.length;
    items.push({
      name,
      category: '',
      unit: normalizeUnit(m[0]),
      quantity: parseInt(nums[n - 2], 10),
      unitPrice: n >= 3 ? krNum(nums[n - 3]) : undefined,
      discount: n >= 4 ? krNum(nums[n - 4]) : undefined,
      total: krNum(nums[n - 1]),
    });
  }

  return { items, recipes, unreadable };
}

export function parseNemlig(raw: string): ParseResult {
  const lines = raw.split(/\r?\n/);
  return isFormatA(lines) ? parseFormatA(lines) : parseFormatB(lines);
}
