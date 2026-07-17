import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const body = await request.json();
	try {
		const recipe = await api.createRecipe(body);
		return new Response(JSON.stringify(recipe), { status: 201, headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'create' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
