import type { Dish } from './api.types';

/** Normalisér til sammenligning: trim, lowercase, fold ø/å/æ, kollaps whitespace. */
export function normalizeTitle(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/ø/g, 'o')
    .replace(/å/g, 'a')
    .replace(/æ/g, 'ae')
    .replace(/\s+/g, ' ');
}

/** Id på en ret hvis navnet matcher titlen (normaliseret), ellers null. */
export function matchDish(title: string, dishes: Dish[]): number | null {
  const key = normalizeTitle(title);
  if (!key) return null;
  const hit = dishes.find((d) => normalizeTitle(d.name) === key);
  return hit ? hit.id : null;
}
