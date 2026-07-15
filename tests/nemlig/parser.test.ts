import { describe, it, expect } from 'vitest';
import { parseNemlig } from '../../src/lib/nemlig/parser';
import { defaultLocationForCategory } from '../../src/lib/locations';

const FORMAT_A = `Drikke
Læskedrik m. hyldeblomstsmag
1 l
1
8,50 kr.
8,50 kr.
Frost
Rustik baguette øko.
350 g
1
19,96 kr.
4,99 kr.
19,96 kr.
Køl
Letmælk 1,5%
1 l
4
10,95 kr.
43,80 kr.`;

const FORMAT_B = `Letmælk 1,5% 1 l 10,95 4 43,80
Mascarpone 250 g 8,24 24,71 1 24,71
Rustik baguette øko. 350 g 4,99 19,96 1 19,96
Cremet pasta med salsiccia 4 personer 0 0,00
Varer i alt kr. 888,48
Total (heraf 25% moms kr. 188,06) kr. 940,28`;

describe('Format A — rå lodret tekst', () => {
  const r = parseNemlig(FORMAT_A);

  it('parses 3 items with names', () => {
    expect(r.items.map((i) => i.name)).toEqual([
      'Læskedrik m. hyldeblomstsmag',
      'Rustik baguette øko.',
      'Letmælk 1,5%',
    ]);
  });

  it('assigns categories from headers', () => {
    expect(r.items.map((i) => i.category)).toEqual(['Drikke', 'Frost', 'Køl']);
  });

  it('parses unit + integer quantity', () => {
    expect(r.items.map((i) => i.unit)).toEqual(['1 l', '350 g', '1 l']);
    expect(r.items.map((i) => i.quantity)).toEqual([1, 1, 4]);
  });

  it('maps kr-lines: 2 lines = [stk,total], 3 lines = [stk,rabat,total]', () => {
    expect(r.items[0]).toMatchObject({ unitPrice: 8.5, discount: undefined, total: 8.5 });
    expect(r.items[1]).toMatchObject({ unitPrice: 19.96, discount: 4.99, total: 19.96 });
    expect(r.items[2]).toMatchObject({ unitPrice: 10.95, discount: undefined, total: 43.8 });
  });

  it('finds no recipes or unreadable lines in this fixture', () => {
    expect(r.recipes).toEqual([]);
    expect(r.unreadable).toEqual([]);
  });
});

describe('Format B — kolonner fra PDF', () => {
  const r = parseNemlig(FORMAT_B);

  it('parses 3 inventory items (recipe + totals excluded)', () => {
    expect(r.items.map((i) => i.name)).toEqual([
      'Letmælk 1,5%',
      'Mascarpone',
      'Rustik baguette øko.',
    ]);
  });

  it('extracts unit and integer quantity before price', () => {
    expect(r.items[0]).toMatchObject({ unit: '1 l', quantity: 4, total: 43.8, unitPrice: 10.95 });
    expect(r.items[1]).toMatchObject({ unit: '250 g', quantity: 1, total: 24.71, unitPrice: 24.71, discount: 8.24 });
    expect(r.items[2]).toMatchObject({ unit: '350 g', quantity: 1, total: 19.96, unitPrice: 19.96, discount: 4.99 });
  });

  it('captures recipe lines separately', () => {
    expect(r.recipes).toEqual([{ name: 'Cremet pasta med salsiccia', persons: 4 }]);
  });

  it('ignores footer/total lines (none leak into items)', () => {
    expect(r.items.some((i) => /Varer i alt|Total/.test(i.name))).toBe(false);
  });
});

describe('parse + default-mapping = BILAG forventet resultat', () => {
  it('suggests the documented locations for Format A items', () => {
    const r = parseNemlig(FORMAT_A);
    const suggested = r.items.map((i) => defaultLocationForCategory(i.category));
    expect(suggested).toEqual(['skab', 'fryser', 'koleskab']);
  });
});

describe('robustness', () => {
  it('skips an intro header block before the first category', () => {
    const withHeader = `Fleksibel levering\n17. juni 2026\nVarenavn Enhed Antal Pris\n${FORMAT_A}`;
    const r = parseNemlig(withHeader);
    expect(r.items.map((i) => i.name)).toEqual([
      'Læskedrik m. hyldeblomstsmag',
      'Rustik baguette øko.',
      'Letmælk 1,5%',
    ]);
  });
});
