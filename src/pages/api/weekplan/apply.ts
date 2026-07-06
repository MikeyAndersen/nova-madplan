import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
import type { ApplyDecision, ApplyResult } from '../../../lib/weekplan-preview';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const body = (await request.json().catch(() => ({}))) as { weekStart?: string; decisions?: ApplyDecision[] };
	let cooked = new Set<string>();
	try {
		const week = body.weekStart ? await api.getWeekplan(body.weekStart) : await api.getCurrentWeekplan();
		cooked = new Set(week.days.filter((d) => d.status === 'cooked').map((d) => d.date));
	} catch { /* uden uge-data springer vi cooked-låsen over (best-effort) */ }
	const results: ApplyResult[] = [];
	for (const d of body.decisions ?? []) {
		if (d.action === 'skip') {
			results.push({ date: d.date, ok: true });
			continue;
		}
		if (cooked.has(d.date)) {
			results.push({ date: d.date, ok: true });
			continue;
		}
		try {
			let dishId: number | null = null;
			let note: string | null = null;
			if (d.action === 'use_dish') dishId = d.dishId ?? null;
			else if (d.action === 'create_dish') dishId = (await api.createDish({ name: (d.title ?? '').trim() })).id;
			else if (d.action === 'note') note = (d.title ?? '').trim() || null;
			await api.putDay({ date: d.date, status: 'planned', dish_id: dishId, note });
			results.push({ date: d.date, ok: true });
		} catch (e) {
			results.push({ date: d.date, ok: false, error: e instanceof Error ? e.message : 'fejl' });
		}
	}
	return Response.json({ results });
};
