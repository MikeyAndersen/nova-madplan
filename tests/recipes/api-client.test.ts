import { describe, it, expect, vi } from 'vitest';
import { makeApi } from '../../src/lib/api';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

describe('recipe api methods', () => {
	it('scrapeRecipe posts url and returns preview', async () => {
		const fetchImpl = vi.fn(async () =>
			jsonResponse({ parsed: { title: 'Kødsovs', ingredients: [], steps: [] }, ok: true, image_url: null }));
		const api = makeApi('http://b', 't', fetchImpl as unknown as typeof fetch);
		const prev = await api.scrapeRecipe('https://x/r');
		expect(prev.parsed.title).toBe('Kødsovs');
		const [url, init] = fetchImpl.mock.calls[0];
		expect(url).toBe('http://b/api/recipes/scrape');
		expect((init as RequestInit).method).toBe('POST');
		expect(JSON.parse((init as RequestInit).body as string)).toEqual({ url: 'https://x/r' });
	});

	it('listRecipes builds q query', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse([]));
		const api = makeApi('http://b', 't', fetchImpl as unknown as typeof fetch);
		await api.listRecipes('taco');
		expect(fetchImpl.mock.calls[0][0]).toBe('http://b/api/recipes?q=taco');
	});

	it('createRecipe POSTs body; deleteRecipe tolerates 204', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ id: 5, title: 'X' }, 201));
		const api = makeApi('http://b', 't', fetchImpl as unknown as typeof fetch);
		const r = await api.createRecipe({ title: 'X' });
		expect(r.id).toBe(5);
		expect((fetchImpl.mock.calls[0][1] as RequestInit).method).toBe('POST');

		const del = vi.fn(async () => new Response(null, { status: 204 }));
		const api2 = makeApi('http://b', 't', del as unknown as typeof fetch);
		await expect(api2.deleteRecipe(5)).resolves.toBeUndefined();
		expect((del.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
	});
});
