import type { APIRoute } from 'astro';
import { getApi } from '../../../lib/api';
import { parseWeekPlan } from '../../../lib/weekplan';
import { buildPreview } from '../../../lib/weekplan-preview';

export const POST: APIRoute = async ({ request }) => {
	const api = await getApi();
	const body = (await request.json().catch(() => ({}))) as { weekStart?: string; raw?: string };
	try {
		const week = body.weekStart ? await api.getWeekplan(body.weekStart) : await api.getCurrentWeekplan();
		const dishes = await api.listDishes(false);
		const days = buildPreview(parseWeekPlan(body.raw ?? ''), week, dishes);
		return Response.json({ week_start: week.week_start, days });
	} catch {
		return Response.json({ error: 'preview_failed' }, { status: 502 });
	}
};
