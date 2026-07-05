import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const GET: APIRoute = async () => {
	const api = await getApi();
	try {
		const s = await api.getSuggestions();
		return new Response(JSON.stringify({ updated_at: s.updated_at }), { status: 200 });
	} catch {
		return new Response(JSON.stringify({ updated_at: null }), { status: 502 });
	}
};
