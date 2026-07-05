import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';

function s(d: FormData, k: string): string {
	return String(d.get(k) ?? '').trim();
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const action = s(data, 'action');
	try {
		if (action === 'create') {
			await api.createDish({ name: s(data, 'name'), recurring_weekly: s(data, 'recurring_weekly') === '1' });
		} else if (action === 'update') {
			const id = Number(s(data, 'id'));
			await api.updateDish(id, { name: s(data, 'name'), recurring_weekly: s(data, 'recurring_weekly') === '1' });
		} else if (action === 'toggle') {
			await api.updateDish(Number(s(data, 'id')), { active: s(data, 'active') === '1' });
		} else if (action === 'recurring') {
			await api.updateDish(Number(s(data, 'id')), { recurring_weekly: s(data, 'recurring_weekly') === '1' });
		} else if (action === 'delete') {
			await api.deleteDish(Number(s(data, 'id')));
		}
	} catch {
		return redirect('/retter?error=1');
	}
	return redirect('/retter');
};
