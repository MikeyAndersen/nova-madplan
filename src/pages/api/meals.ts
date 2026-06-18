import type { APIRoute } from 'astro';
import { env } from 'cloudflare:workers';
import { upsertMeal, toggleFlex, createUpcomingWeek, setWeekTitles } from '../../lib/db';
import { parseWeekPlan } from '../../lib/weekplan';

function str(data: FormData, key: string): string {
  return String(data.get(key) ?? '').trim();
}
function nullable(data: FormData, key: string): string | null {
  const v = str(data, key);
  return v === '' ? null : v;
}

export const POST: APIRoute = async ({ request, redirect }) => {
  const db = env.DB;
  const data = await request.formData();
  const action = str(data, 'action');

  if (action === 'upsert') {
    const weekId = Number(str(data, 'weekId'));
    const weekday = Number(str(data, 'weekday'));
    if (weekId && weekday >= 1 && weekday <= 7) {
      await upsertMeal(db, {
        weekId,
        weekday,
        title: nullable(data, 'title'),
        isFlex: str(data, 'is_flex') === '1',
        notes: nullable(data, 'notes'),
        cook: nullable(data, 'cook'),
        recipeUrl: nullable(data, 'recipe_url'),
      });
    }
  } else if (action === 'toggleFlex') {
    const weekId = Number(str(data, 'weekId'));
    const weekday = Number(str(data, 'weekday'));
    if (weekId && weekday >= 1 && weekday <= 7) await toggleFlex(db, weekId, weekday);
  } else if (action === 'quickfill') {
    const weekId = Number(str(data, 'weekId'));
    const raw = String(data.get('raw') ?? '');
    if (weekId) await setWeekTitles(db, weekId, parseWeekPlan(raw));
  } else if (action === 'createUpcoming') {
    await createUpcomingWeek(db);
  }

  const referer = request.headers.get('referer');
  return redirect(referer ?? '/madplan');
};
