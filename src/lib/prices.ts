// Ren logik til prishistorik: gruppér rå pris-rækker pr. vare og udled trend.

export interface PriceRow {
  name: string;
  name_key: string; // normaliseret navn til gruppering
  unit: string | null;
  unit_price: number;
  recorded_at: string; // ISO-dato
}

export interface PriceTrend {
  name: string;
  unit: string | null;
  latest: number;
  latestDate: string;
  previous: number | null;
  change: 'up' | 'down' | 'same' | null;
  min: number;
  max: number;
  points: { date: string; price: number }[]; // nyeste først
}

export function summarizePrices(rows: PriceRow[]): PriceTrend[] {
  const groups = new Map<string, PriceRow[]>();
  for (const r of rows) {
    const list = groups.get(r.name_key);
    if (list) list.push(r);
    else groups.set(r.name_key, [r]);
  }

  const result: PriceTrend[] = [];
  for (const rs of groups.values()) {
    const sorted = [...rs].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
    const prices = sorted.map((r) => r.unit_price);
    const latest = sorted[0];
    const previous = sorted[1]?.unit_price ?? null;
    let change: PriceTrend['change'] = null;
    if (previous !== null) {
      change = latest.unit_price > previous ? 'up' : latest.unit_price < previous ? 'down' : 'same';
    }
    result.push({
      name: latest.name,
      unit: latest.unit,
      latest: latest.unit_price,
      latestDate: latest.recorded_at,
      previous,
      change,
      min: Math.min(...prices),
      max: Math.max(...prices),
      points: sorted.map((r) => ({ date: r.recorded_at, price: r.unit_price })),
    });
  }

  result.sort((a, b) => a.name.localeCompare(b.name, 'da'));
  return result;
}

export function formatKr(n: number): string {
  return (
    n.toLocaleString('da-DK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' kr.'
  );
}
