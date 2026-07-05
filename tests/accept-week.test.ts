import { describe, it, expect } from 'vitest';
import { daysToAccept } from '../src/lib/accept-week';
import type { SuggestionSet, WeekPlan } from '../src/lib/api.types';

const sugg = (date: string, dish_id: number) => ({ date, dish_id, dish_name: 'x', reason: 'r', confidence: 0.5 });
const day = (date: string, status: string) => ({ date, weekday: 'x', dish_id: 1, dish_name: 'd', status, note: null });

describe('daysToAccept', () => {
	it('skips days already planned or cooked; keeps empty/skipped', () => {
		const set = { suggestions: [sugg('2026-07-13', 3), sugg('2026-07-14', 4), sugg('2026-07-15', 5)] } as SuggestionSet;
		const wp = { days: [day('2026-07-13', 'planned'), day('2026-07-14', 'cooked'), day('2026-07-15', 'empty')] } as unknown as WeekPlan;
		const out = daysToAccept(set, wp);
		expect(out.map((s) => s.date)).toEqual(['2026-07-15']);
	});

	it('accepts all when weekplan has no matching planned days', () => {
		const set = { suggestions: [sugg('2026-07-13', 3)] } as SuggestionSet;
		const wp = { days: [day('2026-07-13', 'skipped')] } as unknown as WeekPlan;
		expect(daysToAccept(set, wp)).toHaveLength(1);
	});
});
