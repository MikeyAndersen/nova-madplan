import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async ({ redirect }) => {
	const api = await getApi();
	try {
		await api.resetRejections();
	} catch {
		return redirect('/forslag?error=1');
	}
	return redirect('/forslag');
};
