import type { WeekPlan, Dish } from './api.types';
import type { WeekPlanEntry } from './weekplan';
import { matchDish } from './weekplan-match';

export type PreviewKind = 'match' | 'new' | 'conflict' | 'cooked' | 'keep' | 'empty';

export interface PreviewDay {
  date: string;
  weekday: number; // 1=man … 7=søn
  parsedTitle?: string;
  kind: PreviewKind;
  matchedDishId?: number;
  matchedDishName?: string;
  currentDishName?: string;
}

export interface ApplyDecision {
  date: string;
  action: 'create_dish' | 'use_dish' | 'note' | 'skip';
  dishId?: number;
  title?: string;
}

export interface ApplyResult {
  date: string;
  ok: boolean;
  error?: string;
}

/** Sammensæt preview pr. dag ud fra parsede linjer + ugens nuværende tilstand. */
export function buildPreview(parsed: WeekPlanEntry[], week: WeekPlan, dishes: Dish[]): PreviewDay[] {
  const byDay = new Map<number, string>(parsed.map((e) => [e.weekday, e.title]));
  return week.days.map((day, i) => {
    const weekday = i + 1;
    const currentDishName = day.dish_name ?? undefined;
    const title = byDay.get(weekday);

    if (day.status === 'cooked') {
      return { date: day.date, weekday, kind: 'cooked', currentDishName };
    }
    if (title == null) {
      const kind: PreviewKind = day.status === 'planned' ? 'keep' : 'empty';
      return { date: day.date, weekday, kind, currentDishName };
    }
    const matchId = matchDish(title, dishes);
    const matched = matchId != null ? dishes.find((d) => d.id === matchId) : undefined;
    if (day.status === 'planned') {
      return {
        date: day.date, weekday, parsedTitle: title, kind: 'conflict',
        currentDishName,
        matchedDishId: matchId ?? undefined, matchedDishName: matched?.name,
      };
    }
    if (matchId != null) {
      return {
        date: day.date, weekday, parsedTitle: title, kind: 'match',
        matchedDishId: matchId, matchedDishName: matched?.name,
      };
    }
    return { date: day.date, weekday, parsedTitle: title, kind: 'new' };
  });
}
