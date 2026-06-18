import { describe, it, expect } from 'vitest';
import { summarizePrices, formatKr, type PriceRow } from '../src/lib/prices';

const rows: PriceRow[] = [
  { name: 'Letmælk 1,5%', name_key: 'letmælk 1,5%', unit: '1 l', unit_price: 11.5, recorded_at: '2026-06-01' },
  { name: 'Letmælk 1,5%', name_key: 'letmælk 1,5%', unit: '1 l', unit_price: 10.95, recorded_at: '2026-05-01' },
  { name: 'Smør', name_key: 'smør', unit: '200 g', unit_price: 18.0, recorded_at: '2026-06-01' },
];

describe('summarizePrices', () => {
  const out = summarizePrices(rows);

  it('groups by name_key and sorts groups by name', () => {
    expect(out.map((o) => o.name)).toEqual(['Letmælk 1,5%', 'Smør']);
  });

  it('reports latest price/date, newest-first points, min and max', () => {
    const milk = out[0];
    expect(milk.latest).toBe(11.5);
    expect(milk.latestDate).toBe('2026-06-01');
    expect(milk.previous).toBe(10.95);
    expect(milk.min).toBe(10.95);
    expect(milk.max).toBe(11.5);
    expect(milk.points.map((p) => p.date)).toEqual(['2026-06-01', '2026-05-01']);
  });

  it('marks a price rise as "up" and a single data point as null', () => {
    expect(out[0].change).toBe('up');
    expect(out[1].previous).toBeNull();
    expect(out[1].change).toBeNull();
  });

  it('marks a price drop as "down"', () => {
    const dropping: PriceRow[] = [
      { name: 'Æg', name_key: 'æg', unit: '10 stk.', unit_price: 30, recorded_at: '2026-06-01' },
      { name: 'Æg', name_key: 'æg', unit: '10 stk.', unit_price: 35, recorded_at: '2026-05-01' },
    ];
    expect(summarizePrices(dropping)[0].change).toBe('down');
  });
});

describe('formatKr', () => {
  it('formats Danish currency', () => {
    expect(formatKr(10.95)).toBe('10,95 kr.');
    expect(formatKr(8)).toBe('8,00 kr.');
  });
});
