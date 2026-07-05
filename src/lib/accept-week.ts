import type { SuggestionSet, WeekPlan, Suggestion } from './api.types';

/** Menneske-vinder (§2.4): spring dage over der allerede er planned/cooked. */
export function daysToAccept(set: SuggestionSet, plan: WeekPlan): Suggestion[] {
	const locked = new Set(
		plan.days.filter((d) => d.status === 'planned' || d.status === 'cooked').map((d) => d.date),
	);
	return set.suggestions.filter((s) => !locked.has(s.date));
}
