import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
import { daysToAccept } from '../../../lib/accept-week';

function s(d: FormData, k: string): string {
	return String(d.get(k) ?? '').trim();
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	try {
		if (s(data, 'all') === '1') {
			const set = await api.getSuggestions();
			const plan = await api.getWeekplan(s(data, 'week_start'));
			for (const sug of daysToAccept(set, plan)) await api.acceptSuggestion(sug.date, sug.dish_id);
		} else {
			await api.acceptSuggestion(s(data, 'date'), Number(s(data, 'dish_id')));
		}
	} catch {
		return redirect('/forslag?error=1');
	}
	return redirect('/forslag');
};
