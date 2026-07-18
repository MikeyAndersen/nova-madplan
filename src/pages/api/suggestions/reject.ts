import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const dishId = Number(String(data.get('dish_id') ?? ''));
	try {
		if (dishId) await api.rejectSuggestion(dishId);
	} catch {
		return redirect('/forslag?error=1');
	}
	return redirect('/forslag');
};
