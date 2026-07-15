import { describe, it, expect } from 'vitest';
import { defaultLocationForCategory, LOCATION_LABELS } from '../src/lib/locations';

describe('category -> default location (spec §6.6)', () => {
  it('maps known nemlig categories', () => {
    expect(defaultLocationForCategory('Frost')).toBe('fryser');
    expect(defaultLocationForCategory('Køl')).toBe('koleskab');
    expect(defaultLocationForCategory('Mejeri')).toBe('koleskab');
    expect(defaultLocationForCategory('Kød & fisk')).toBe('koleskab');
    expect(defaultLocationForCategory('Grønt')).toBe('koleskab');
    expect(defaultLocationForCategory('Kolonial')).toBe('skab');
    expect(defaultLocationForCategory('Brød')).toBe('skab');
    expect(defaultLocationForCategory('Drikke')).toBe('skab');
    expect(defaultLocationForCategory('Pleje')).toBe('ovrigt');
  });

  it('is case/whitespace-insensitive', () => {
    expect(defaultLocationForCategory('  frost ')).toBe('fryser');
    expect(defaultLocationForCategory('KØL')).toBe('koleskab');
  });

  it('falls back to skab for unknown/empty categories', () => {
    expect(defaultLocationForCategory('Ukendt')).toBe('skab');
    expect(defaultLocationForCategory('')).toBe('skab');
  });

  it('has Danish labels for every location', () => {
    expect(LOCATION_LABELS).toEqual({
      koleskab: 'Køleskab', fryser: 'Fryser', skab: 'Skab', ovrigt: 'Øvrigt',
    });
  });
});
