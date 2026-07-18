import { describe, it, expect } from 'vitest';
import { buildPickerOptions, filterOptions, normalize } from '../src/lib/picker-options';
import type { Dish, Recipe } from '../src/lib/api.types';

function dish(p: Partial<Dish> & { id: number; name: string }): Dish {
	return { tags: [], recurring_weekly: false, ingredients: [], last_made: null, active: true, ...p };
}
function recipe(p: Partial<Recipe> & { id: number; title: string }): Recipe {
	return { source_url: null, ingredients: [], steps: [], time_min: null, tags: [], raw_snapshot: '', has_image: false, created_at: '', updated_at: '', ...p };
}

describe('buildPickerOptions', () => {
	it('badges dishes with recipe + ai, dedupes linked recipes', () => {
		const dishes = [
			dish({ id: 1, name: 'Kødsovs', recipe_id: 10 }),
			dish({ id: 2, name: 'Tacos' }),
		];
		const recipes = [recipe({ id: 10, title: 'Kødsovs' }), recipe({ id: 11, title: 'Karbonader' })];
		const opts = buildPickerOptions(dishes, recipes, new Set([1]), new Map([[1, 5], [2, 1]]));

		const kodsovs = opts.find((o) => o.label === 'Kødsovs')!;
		expect(kodsovs.kind).toBe('dish');
		expect(kodsovs.badges.sort()).toEqual(['ai', 'opskrift', 'ret']);

		// recipe 10 is linked to a dish → not a separate entry; 11 is standalone
		expect(opts.filter((o) => o.kind === 'recipe').map((o) => o.label)).toEqual(['Karbonader']);
		const karbonader = opts.find((o) => o.label === 'Karbonader')!;
		expect(karbonader.recipeId).toBe(11);
		expect(karbonader.badges).toEqual(['opskrift']);
	});

	it('ranks ai first, then by timesMade', () => {
		const dishes = [
			dish({ id: 1, name: 'Sjælden' }),
			dish({ id: 2, name: 'Ofte' }),
			dish({ id: 3, name: 'AI-valg' }),
		];
		const opts = buildPickerOptions(dishes, [], new Set([3]), new Map([[1, 0], [2, 9], [3, 1]]));
		expect(opts.map((o) => o.dishId)).toEqual([3, 2, 1]);
	});

	it('excludes inactive dishes', () => {
		const opts = buildPickerOptions([dish({ id: 1, name: 'Væk', active: false })], [], new Set(), new Map());
		expect(opts).toEqual([]);
	});
});

describe('filterOptions / normalize', () => {
	it('matches accent-insensitively', () => {
		expect(normalize('Kødsovs')).toBe('kodsovs');
		const opts = buildPickerOptions([dish({ id: 1, name: 'Kødsovs' })], [], new Set(), new Map());
		expect(filterOptions(opts, 'kods').map((o) => o.label)).toEqual(['Kødsovs']);
		expect(filterOptions(opts, 'xyz')).toEqual([]);
	});
});
