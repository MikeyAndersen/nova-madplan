import { describe, it, expect, vi } from 'vitest';
import { makeApi } from '../src/lib/api';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

describe('makeApi inventory', () => {
	it('listInventory builds query and parses list', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse([{ id: 1, name: 'Smør' }]));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		const items = await api.listInventory({ q: 'smø', category: 'koleskab' });
		expect(items[0].name).toBe('Smør');
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/inventory?q=sm%C3%B8&category=koleskab');
	});

	it('listInventory without filter hits bare path', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse([]));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await api.listInventory();
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/inventory');
	});

	it('bulkAddInventory POSTs items+merge', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ added: 1, merged: 0 }, 201));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		const res = await api.bulkAddInventory([{ name: 'Ris' }], false);
		expect(res).toEqual({ added: 1, merged: 0 });
		const [url, init] = fetchImpl.mock.calls[0];
		expect(url).toBe('http://b/api/inventory');
		expect((init as RequestInit).method).toBe('POST');
		expect(JSON.parse((init as RequestInit).body as string)).toEqual({ items: [{ name: 'Ris' }], merge: false });
	});

	it('updateInventoryItem PATCHes; deleteInventoryItem tolerates 204', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ id: 3, quantity: 2 }));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await api.updateInventoryItem(3, { quantity: 2 });
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/inventory/3');
		expect((fetchImpl.mock.calls[0][1] as RequestInit).method).toBe('PATCH');

		const del = vi.fn(async () => new Response(null, { status: 204 }));
		const api2 = makeApi('http://b', 's', del as unknown as typeof fetch);
		await expect(api2.deleteInventoryItem(3)).resolves.toBeUndefined();
		expect((del.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
	});
});
