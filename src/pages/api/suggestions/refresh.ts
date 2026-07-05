import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async () => {
	const api = await getApi();
	try {
		await api.refreshSuggestions();
		return new Response(JSON.stringify({ status: 'accepted' }), { status: 202 });
	} catch {
		return new Response(JSON.stringify({ status: 'error' }), { status: 502 });
	}
};
