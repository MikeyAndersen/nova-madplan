// tests/weekplan-preview.test.ts
import { describe, it, expect } from 'vitest';
import { buildPreview } from '../src/lib/weekplan-preview';
import type { WeekPlan, Day, Dish } from '../src/lib/api.types';

const dish = (id: number, name: string): Dish => ({
  id, name, tags: [], recurring_weekly: false, ingredients: [], last_made: null, active: true,
});
const day = (date: string, weekday: string, over: Partial<Day> = {}): Day => ({
  date, weekday, dish_id: null, dish_name: null, status: 'empty', note: null, ...over,
});
// Uge med mandag=2026-07-06 … søndag=2026-07-12
const week = (days: Day[]): WeekPlan => ({ week_start: '2026-07-06', days, updated_at: '' });
const DATES = ['2026-07-06','2026-07-07','2026-07-08','2026-07-09','2026-07-10','2026-07-11','2026-07-12'];
const WD = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
const emptyWeek = () => week(DATES.map((d, i) => day(d, WD[i])));

const dishes = [dish(3, 'Kødsovs')];

describe('buildPreview', () => {
  it('match: kendt ret på en tom dag', () => {
    const p = buildPreview([{ weekday: 1, title: 'kødsovs' }], emptyWeek(), dishes);
    expect(p[0]).toMatchObject({ date: '2026-07-06', weekday: 1, kind: 'match', matchedDishId: 3 });
  });

  it('new: ukendt titel på en tom dag', () => {
    const p = buildPreview([{ weekday: 2, title: 'Tacos' }], emptyWeek(), dishes);
    expect(p[1]).toMatchObject({ weekday: 2, kind: 'new', parsedTitle: 'Tacos' });
  });

  it('conflict: paste rammer en allerede planlagt dag', () => {
    const w = emptyWeek();
    w.days[2] = day(DATES[2], WD[2], { status: 'planned', dish_id: 9, dish_name: 'Pizza' });
    const p = buildPreview([{ weekday: 3, title: 'Kødsovs' }], w, dishes);
    expect(p[2]).toMatchObject({ weekday: 3, kind: 'conflict', currentDishName: 'Pizza', matchedDishId: 3 });
  });

  it('cooked: låst uanset paste', () => {
    const w = emptyWeek();
    w.days[3] = day(DATES[3], WD[3], { status: 'cooked', dish_id: 5, dish_name: 'Suppe' });
    const p = buildPreview([{ weekday: 4, title: 'Kødsovs' }], w, dishes);
    expect(p[3]).toMatchObject({ weekday: 4, kind: 'cooked', currentDishName: 'Suppe' });
  });

  it('keep: planlagt dag uden paste-linje', () => {
    const w = emptyWeek();
    w.days[4] = day(DATES[4], WD[4], { status: 'planned', dish_id: 9, dish_name: 'Pizza' });
    const p = buildPreview([], w, dishes);
    expect(p[4]).toMatchObject({ weekday: 5, kind: 'keep', currentDishName: 'Pizza' });
  });

  it('empty: tom dag uden paste-linje', () => {
    const p = buildPreview([], emptyWeek(), dishes);
    expect(p[6]).toMatchObject({ weekday: 7, kind: 'empty' });
  });
});
