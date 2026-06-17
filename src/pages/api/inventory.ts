import type { APIRoute } from 'astro';
import { env } from 'cloudflare:workers';
import { addItem, updateItem, consumeItem, deleteItem } from '../../lib/db';
import { isLocation } from '../../lib/locations';

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

  if (action === 'add') {
    const location = str(data, 'location');
    if (!str(data, 'name') || !isLocation(location)) return redirect('/beholdning');
    await addItem(db, {
      name: str(data, 'name'),
      location,
      category: nullable(data, 'category'),
      unit: nullable(data, 'unit'),
      quantity: Number(str(data, 'quantity')) || 1,
      best_before: nullable(data, 'best_before'),
      source: 'manuel',
    });
  } else if (action === 'update') {
    const id = Number(str(data, 'id'));
    const location = str(data, 'location');
    if (id && isLocation(location)) {
      await updateItem(db, id, {
        name: str(data, 'name'),
        location,
        category: nullable(data, 'category'),
        unit: nullable(data, 'unit'),
        quantity: Number(str(data, 'quantity')) || 0,
        best_before: nullable(data, 'best_before'),
      });
    }
  } else if (action === 'consume') {
    const id = Number(str(data, 'id'));
    if (id) await consumeItem(db, id);
  } else if (action === 'delete') {
    const id = Number(str(data, 'id'));
    if (id) await deleteItem(db, id);
  }

  const referer = request.headers.get('referer');
  return redirect(referer ?? '/beholdning');
};
