import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
import { isLocation } from '../../lib/locations';

function s(d: FormData, k: string): string {
	return String(d.get(k) ?? '').trim();
}
function nullable(d: FormData, k: string): string | null {
	const v = s(d, k);
	return v === '' ? null : v;
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const action = s(data, 'action');
	const back = request.headers.get('referer') ?? '/beholdning';
	try {
		if (action === 'add') {
			if (!s(data, 'name')) return redirect(back);
			const category = s(data, 'category');
			const qtyRaw = s(data, 'quantity');
			const quantity = qtyRaw === '' || Number.isNaN(Number(qtyRaw)) ? 1 : Number(qtyRaw);
			await api.bulkAddInventory([{
				name: s(data, 'name'),
				quantity,
				unit: nullable(data, 'unit'),
				note: nullable(data, 'note'),
				category: isLocation(category) ? category : null,
				source: 'manuel',
			}], true);
		} else if (action === 'update') {
			const id = Number(s(data, 'id'));
			const category = s(data, 'category');
			if (id) {
				await api.updateInventoryItem(id, {
					name: s(data, 'name'),
					quantity: Number(s(data, 'quantity')) || 0,
					unit: nullable(data, 'unit'),
					note: nullable(data, 'note'),
					category: isLocation(category) ? category : null,
				});
			}
		} else if (action === 'consume') {
			const id = Number(s(data, 'id'));
			const qty = Number(s(data, 'quantity')) || 0;
			if (id) {
				if (qty - 1 <= 0) await api.deleteInventoryItem(id);
				else await api.updateInventoryItem(id, { quantity: qty - 1 });
			}
		} else if (action === 'delete') {
			const id = Number(s(data, 'id'));
			if (id) await api.deleteInventoryItem(id);
		}
	} catch {
		return redirect('/beholdning?error=1');
	}
	return redirect(back);
};
