import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async () => {
	const api = await getApi();
	try {
		await api.rejectAllSuggestions();
		return new Response(JSON.stringify({ status: 'accepted' }), { status: 202, headers: { 'content-type': 'application/json' } });
	} catch {
		return new Response(JSON.stringify({ error: 'reject-all' }), { status: 500, headers: { 'content-type': 'application/json' } });
	}
};
