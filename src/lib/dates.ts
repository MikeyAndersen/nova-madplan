// ISO-uge-matematik og dansk datoformatering. Alt regnes i UTC for at undgå
// at tidszoner flytter en dato en dag.

export const WEEKDAYS_DA = [
  'Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lørdag', 'Søndag',
] as const;

const DAY_MS = 86_400_000;

/** UTC-dato (midnat) fra et Date — fjerner tidskomponent. */
function utcMidnight(d: Date): Date {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

/** Parse "YYYY-MM-DD" til UTC-midnat. */
function parseISO(s: string): Date {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

/** Formater en UTC-dato som "YYYY-MM-DD". */
function ymd(d: Date): string {
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** ISO-ugedag: 1=mandag … 7=søndag. */
function isoWeekday(d: Date): number {
  const wd = d.getUTCDay(); // 0=søndag … 6=lørdag
  return wd === 0 ? 7 : wd;
}

/** Mandagens dato (ISO YYYY-MM-DD) for ugen som d ligger i. */
export function mondayOf(d: Date): string {
  const base = utcMidnight(d);
  base.setUTCDate(base.getUTCDate() - (isoWeekday(base) - 1));
  return ymd(base);
}

/** ISO-årstal og ugenummer for en dato (Torsdags-metoden). */
export function isoWeek(d: Date): { year: number; week: number } {
  const date = utcMidnight(d);
  // Flyt til torsdag i samme uge — torsdagen bestemmer ISO-året.
  date.setUTCDate(date.getUTCDate() + (4 - isoWeekday(date)));
  const year = date.getUTCFullYear();
  const jan1 = new Date(Date.UTC(year, 0, 1));
  const week = Math.floor((date.getTime() - jan1.getTime()) / DAY_MS / 7) + 1;
  return { year, week };
}

/** Udled ugens status ud fra mandagens dato (status gemmes aldrig). */
export function weekStatus(
  startDateISO: string,
  today: Date = new Date(),
): 'historisk' | 'nuvaerende' | 'kommende' {
  const monday = parseISO(startDateISO);
  const sunday = new Date(monday);
  sunday.setUTCDate(sunday.getUTCDate() + 6);
  const t = utcMidnight(today);
  if (sunday.getTime() < t.getTime()) return 'historisk';
  if (monday.getTime() > t.getTime()) return 'kommende';
  return 'nuvaerende';
}

/** year/week/start_date for ugen efter den givne mandag. */
export function nextWeekStart(fromMondayISO: string): {
  year: number;
  week: number;
  start_date: string;
} {
  const monday = parseISO(fromMondayISO);
  monday.setUTCDate(monday.getUTCDate() + 7);
  return { ...isoWeek(monday), start_date: ymd(monday) };
}

/** Dansk datoformat, fx "torsdag 18. jun." */
export function formatDa(iso: string): string {
  return new Intl.DateTimeFormat('da-DK', {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(parseISO(iso));
}

/** I dag som ISO YYYY-MM-DD (UTC). */
export function todayISO(): string {
  return ymd(new Date());
}

/** Læg n dage til en ISO-dato. */
export function addDaysISO(iso: string, n: number): string {
  const d = parseISO(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return ymd(d);
}

/** Kort dansk dag+måned, fx "15. jun." */
export function dayMonthDa(iso: string): string {
  return new Intl.DateTimeFormat('da-DK', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(parseISO(iso));
}
