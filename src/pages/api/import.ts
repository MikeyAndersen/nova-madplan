import type { APIRoute } from 'astro';
import { env } from 'cloudflare:workers';
import { addItem, mergeOrInsert, getCurrentWeek, suggestMeal, type NewItem } from '../../lib/db';
import { isLocation } from '../../lib/locations';

function field(data: FormData, key: string): string {
  return String(data.get(key) ?? '').trim();
}
function nullableField(data: FormData, key: string): string | null {
  const v = field(data, key);
  return v === '' ? null : v;
}

export const POST: APIRoute = async ({ request, redirect }) => {
  const db = env.DB;
  const data = await request.formData();

  const included = data.getAll('include').map((v) => Number(v)).filter((n) => !Number.isNaN(n));

  let added = 0;
  let ovrigt = 0;

  for (const i of included) {
    const name = field(data, `name_${i}`);
    const location = field(data, `location_${i}`);
    if (!name || !isLocation(location)) continue;

    const item: NewItem = {
      name,
      location,
      quantity: Number(field(data, `quantity_${i}`)) || 1,
      unit: nullableField(data, `unit_${i}`),
      category: nullableField(data, `category_${i}`),
      best_before: nullableField(data, `best_before_${i}`),
      source: 'nemlig',
    };

    if (field(data, `merge_${i}`) === '1') {
      await mergeOrInsert(db, item);
    } else {
      await addItem(db, item);
    }
    added++;
    if (location === 'ovrigt') ovrigt++;
  }

  // Opskrifter → forslag i madplanen (denne uge).
  const recipeCount = Number(field(data, 'recipe_count')) || 0;
  let recipesInserted = 0;
  if (recipeCount > 0) {
    let weekId: number | null = null;
    for (let r = 0; r < recipeCount; r++) {
      const day = Number(field(data, `recipe_day_${r}`));
      const name = field(data, `recipe_name_${r}`);
      if (name && day >= 1 && day <= 7) {
        if (weekId === null) weekId = (await getCurrentWeek(db)).id;
        await suggestMeal(db, weekId, day, name);
        recipesInserted++;
      }
    }
  }

  const params = new URLSearchParams({
    added: String(added),
    ovrigt: String(ovrigt),
    recipes: String(recipesInserted),
    skipped: String(recipeCount),
  });
  return redirect(`/import?${params.toString()}`);
};
