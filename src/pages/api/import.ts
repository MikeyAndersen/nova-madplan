import type { APIRoute } from 'astro';
import { getApi } from '../../lib/api';
import { isLocation } from '../../lib/locations';
import type { InventoryItemInput } from '../../lib/api.types';

function field(data: FormData, key: string): string {
	return String(data.get(key) ?? '').trim();
}
function nullableField(data: FormData, key: string): string | null {
	const v = field(data, key);
	return v === '' ? null : v;
}

export const POST: APIRoute = async ({ request, redirect }) => {
	const api = await getApi();
	const data = await request.formData();
	const included = data.getAll('include').map((v) => Number(v)).filter((n) => !Number.isNaN(n));

	const mergeItems: InventoryItemInput[] = [];
	const plainItems: InventoryItemInput[] = [];
	for (const i of included) {
		const name = field(data, `name_${i}`);
		if (!name) continue;
		const location = field(data, `location_${i}`);
		const item: InventoryItemInput = {
			name,
			quantity: Number(field(data, `quantity_${i}`)) || 1,
			unit: nullableField(data, `unit_${i}`),
			category: isLocation(location) ? location : null,
			source: 'nemlig',
		};
		(field(data, `merge_${i}`) === '1' ? mergeItems : plainItems).push(item);
	}

	let added = 0;
	let merged = 0;
	try {
		if (mergeItems.length) {
			const r = await api.bulkAddInventory(mergeItems, true);
			added += r.added;
			merged += r.merged;
		}
		if (plainItems.length) {
			const r = await api.bulkAddInventory(plainItems, false);
			added += r.added;
			merged += r.merged;
		}
	} catch {
		return redirect('/import?error=1');
	}
	const itemCount = Number(field(data, 'item_count')) || 0;
	const params = new URLSearchParams({
		added: String(added),
		merged: String(merged),
		skipped: String(Math.max(itemCount - included.length, 0)),
	});
	return redirect(`/import?${params.toString()}`);
};
