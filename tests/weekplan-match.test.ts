import { describe, it, expect } from 'vitest';
import { normalizeTitle, matchDish } from '../src/lib/weekplan-match';
import type { Dish } from '../src/lib/api.types';

const dish = (id: number, name: string): Dish => ({
  id, name, tags: [], recurring_weekly: false, ingredients: [], last_made: null, active: true,
});

describe('normalizeTitle', () => {
  it('folder case, whitespace og ø/å/æ', () => {
    expect(normalizeTitle('  Kødsovs  ')).toBe('kodsovs');
    expect(normalizeTitle('Rød GRØD')).toBe('rod grod');
    expect(normalizeTitle('Æblekage')).toBe('aeblekage');
  });
});

describe('matchDish', () => {
  const dishes = [dish(3, 'Kødsovs'), dish(7, 'Grøn salat')];
  it('matcher uanset case og æøå', () => {
    expect(matchDish('kodsovs', dishes)).toBe(3);
    expect(matchDish('  KØDSOVS ', dishes)).toBe(3);
  });
  it('returnerer null uden match', () => {
    expect(matchDish('Tacos', dishes)).toBeNull();
  });
  it('returnerer null for tom titel', () => {
    expect(matchDish('   ', dishes)).toBeNull();
  });
});
