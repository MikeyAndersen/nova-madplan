// Parser til "hurtig udfyldning" af en uge: én linje pr. dag i formatet
// "Dag: mad" (fx "Mandag: hel kylling"). Falder tilbage til rækkefølge
// (linje 1 = mandag, …) hvis ingen dag-navne genkendes.

export interface WeekPlanEntry {
  weekday: number; // 1=mandag … 7=søndag
  title: string;
}

const DAY_MAP: Record<string, number> = {
  mandag: 1, man: 1,
  tirsdag: 2, tirs: 2, tir: 2,
  onsdag: 3, ons: 3,
  torsdag: 4, tors: 4, tor: 4,
  fredag: 5, fre: 5,
  lordag: 6, lor: 6,
  sondag: 7, son: 7,
};

function normDay(s: string): string {
  return s.trim().toLowerCase().replace(/ø/g, 'o').replace(/å/g, 'a').replace(/æ/g, 'ae');
}

export function parseWeekPlan(raw: string): WeekPlanEntry[] {
  const lines = raw.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const byDay = new Map<number, string>();
  const plain: string[] = [];
  let matchedAny = false;

  for (const line of lines) {
    const idx = line.indexOf(':');
    if (idx > 0) {
      // Linje med kolon: skal være et rigtigt dag-navn, ellers ignoreres den
      // (fx en mistastet dag eller "Handleliste:"). Bruges aldrig til fallback.
      const weekday = DAY_MAP[normDay(line.slice(0, idx))];
      const title = line.slice(idx + 1).trim();
      if (weekday && title) {
        byDay.set(weekday, title); // sidste linje for samme dag vinder
        matchedAny = true;
      }
      continue;
    }
    plain.push(line); // kun linjer uden kolon kan bruges til rækkefølge-fallback
  }

  // Ingen dag-navne fundet → fordel linjerne i rækkefølge mandag→søndag.
  if (!matchedAny) {
    let weekday = 1;
    for (const line of plain) {
      if (weekday > 7) break;
      byDay.set(weekday, line);
      weekday++;
    }
  }

  return [...byDay.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([weekday, title]) => ({ weekday, title }));
}
