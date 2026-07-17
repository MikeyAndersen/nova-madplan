import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const PATCH: APIRoute = async ({ request, params }) => {
	const api = await getApi();
	const body = await request.json();
	try {
		const recipe = await api.updateRecipe(Number(params.id), body);
		return new Response(JSON.stringify(recipe), { headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'update' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};

export const DELETE: APIRoute = async ({ params }) => {
	const api = await getApi();
	try {
		await api.deleteRecipe(Number(params.id));
		return new Response(null, { status: 204 });
	} catch {
		return new Response(JSON.stringify({ error: 'delete' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
