import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const { url } = await request.json();
	try {
		const preview = await api.scrapeRecipe(String(url ?? ''));
		return new Response(JSON.stringify(preview), { headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'scrape' }), { status: 502, headers: { 'content-type': 'application/json' } });
	}
};
