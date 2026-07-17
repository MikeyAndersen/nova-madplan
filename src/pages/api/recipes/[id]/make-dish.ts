import type { APIRoute } from 'astro';
import { getApi } from '../../../../lib/api';

export const POST: APIRoute = async ({ params }) => {
	const api = await getApi();
	try {
		const recipe = await api.getRecipe(Number(params.id));
		const dish = await api.createDish({ name: recipe.title, ingredients: recipe.ingredients });
		await api.updateDish(dish.id, { recipe_id: recipe.id });
		return new Response(JSON.stringify({ dish_id: dish.id }), { status: 201, headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'make-dish' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
