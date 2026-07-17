import type { APIRoute } from 'astro';
import { getApi } from '../../../../lib/api';

export const POST: APIRoute = async ({ request, params }) => {
	const api = await getApi();
	const { dish_id } = await request.json();
	try {
		await api.updateDish(Number(dish_id), { recipe_id: Number(params.id) });
		return new Response(null, { status: 204 });
	} catch {
		return new Response(JSON.stringify({ error: 'link' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
