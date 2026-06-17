// Lokationer og default-mapping fra nemlig-kategori (spec §6.6).
// Subtype-finesser (rodfrugter -> Skab, frost-mærket kød -> Fryser osv.) er
// overskrivbare defaults: brugeren retter pr. linje på bekræftelsesskærmen.

export const LOCATIONS = ['koleskab', 'fryser', 'skab', 'ovrigt'] as const;
export type Location = (typeof LOCATIONS)[number];

export const LOCATION_LABELS: Record<Location, string> = {
  koleskab: 'Køleskab',
  fryser: 'Fryser',
  skab: 'Skab',
  ovrigt: 'Øvrigt',
};

const CATEGORY_MAP: Record<string, Location> = {
  frost: 'fryser',
  køl: 'koleskab',
  mejeri: 'koleskab',
  'kød & fisk': 'koleskab',
  grønt: 'koleskab',
  kolonial: 'skab',
  brød: 'skab',
  drikke: 'skab',
  pleje: 'ovrigt',
};

export function defaultLocationForCategory(category: string): Location {
  const key = category.trim().toLowerCase();
  return CATEGORY_MAP[key] ?? 'skab';
}

export function isLocation(value: string): value is Location {
  return (LOCATIONS as readonly string[]).includes(value);
}
