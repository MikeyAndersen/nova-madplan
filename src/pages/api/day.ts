import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
import type { DayStatus } from '../../lib/api.types';

function s(d: FormData, k: string): string {
	return String(d.get(k) ?? '').trim();
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const date = s(data, 'date');
	const status = (s(data, 'status') || 'planned') as DayStatus;
	const note = s(data, 'note') || null;
	const back = `/madplan?start=${s(data, 'week_start') || date}`;

	let dishId: number | null = null;
	if (status !== 'empty') {
		const existing = s(data, 'dish_id');
		const recipeId = s(data, 'recipe_id');
		const newName = s(data, 'new_dish_name');
		if (existing) {
			dishId = Number(existing);
		} else if (recipeId) {
			// Opskrift uden ret: opret en ret fra opskriften og link den.
			const recipe = await api.getRecipe(Number(recipeId));
			dishId = (await api.createDish({ name: recipe.title, ingredients: recipe.ingredients, recipe_id: recipe.id })).id;
		} else if (newName) {
			dishId = (await api.createDish({ name: newName })).id;
		}
	}
	try {
		await api.putDay({ date, status, dish_id: dishId, note });
	} catch {
		return redirect(`${back}&error=1`);
	}
	return redirect(back);
};
