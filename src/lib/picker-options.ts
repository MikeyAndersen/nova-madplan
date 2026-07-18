import type { Dish, Recipe } from './api.types';

export type PickerBadge = 'ret' | 'opskrift' | 'ai';

export interface PickerOption {
	label: string;
	kind: 'dish' | 'recipe';
	dishId?: number;
	recipeId?: number;
	badges: PickerBadge[];
	timesMade: number;
}

/** Normalisér til accent/case-ufølsom sammenligning (ø/å/æ-fold). */
export function normalize(s: string): string {
	return String(s || '')
		.trim()
		.toLowerCase()
		.replace(/ø/g, 'o')
		.replace(/å/g, 'a')
		.replace(/æ/g, 'ae')
		.replace(/\s+/g, ' ');
}

/**
 * Byg den samlede, dedupliker­ede optionsliste til ret-vælgeren.
 * - Hver aktiv ret = ét punkt (badge 'ret'; +'opskrift' hvis linket; +'ai' hvis foreslået).
 * - Hver opskrift UDEN en ret der peger på den = ét punkt (badge 'opskrift').
 * Rangering: flest-lavede først, lille løft til AI-foreslåede, alfabetisk tie-break.
 */
export function buildPickerOptions(
	dishes: Dish[],
	recipes: Recipe[],
	suggestionDishIds: Set<number>,
	counts: Map<number, number>,
): PickerOption[] {
	const linkedRecipeIds = new Set<number>();
	for (const d of dishes) if (d.recipe_id != null) linkedRecipeIds.add(d.recipe_id);

	const options: PickerOption[] = [];

	for (const d of dishes) {
		if (!d.active) continue;
		const badges: PickerBadge[] = ['ret'];
		if (d.recipe_id != null) badges.push('opskrift');
		if (suggestionDishIds.has(d.id)) badges.push('ai');
		options.push({
			label: d.name,
			kind: 'dish',
			dishId: d.id,
			badges,
			timesMade: counts.get(d.id) ?? 0,
		});
	}

	for (const r of recipes) {
		if (linkedRecipeIds.has(r.id)) continue; // allerede repræsenteret af sin ret
		options.push({
			label: r.title,
			kind: 'recipe',
			recipeId: r.id,
			badges: ['opskrift'],
			timesMade: 0,
		});
	}

	const aiBoost = (o: PickerOption) => (o.badges.includes('ai') ? 1 : 0);
	options.sort((a, b) => {
		const byAi = aiBoost(b) - aiBoost(a);
		if (byAi) return byAi;
		if (b.timesMade !== a.timesMade) return b.timesMade - a.timesMade;
		return a.label.localeCompare(b.label, 'da');
	});
	return options;
}

/** Filtrér optioner på fritekst (substring, normaliseret). */
export function filterOptions(options: PickerOption[], query: string): PickerOption[] {
	const q = normalize(query);
	if (!q) return options;
	return options.filter((o) => normalize(o.label).includes(q));
}
