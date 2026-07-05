import { describe, it, expect, vi } from 'vitest';
import { makeApi, ApiError } from '../src/lib/api';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

describe('makeApi', () => {
	it('GET current weekplan sends bearer and parses body', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ week_start: '2026-07-06', days: [], updated_at: 'x' }));
		const api = makeApi('http://b', 'secret', fetchImpl as unknown as typeof fetch);
		const wp = await api.getCurrentWeekplan();
		expect(wp.week_start).toBe('2026-07-06');
		const [url, init] = fetchImpl.mock.calls[0];
		expect(url).toBe('http://b/api/weekplan/current');
		expect((init as RequestInit).headers).toMatchObject({ Authorization: 'Bearer secret' });
	});

	it('putDay PUTs JSON to /api/weekplan/day', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ week_start: 'w', days: [], updated_at: 'x' }));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await api.putDay({ date: '2026-07-06', status: 'planned', dish_id: 17, note: null });
		const [url, init] = fetchImpl.mock.calls[0];
		expect(url).toBe('http://b/api/weekplan/day');
		expect((init as RequestInit).method).toBe('PUT');
		expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({ dish_id: 17, status: 'planned' });
	});

	it('deleteDish issues DELETE and tolerates 204 empty body', async () => {
		const fetchImpl = vi.fn(async () => new Response(null, { status: 204 }));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await expect(api.deleteDish(3)).resolves.toBeUndefined();
		expect((fetchImpl.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
	});

	it('throws ApiError with status+detail on non-2xx', async () => {
		const fetchImpl = vi.fn(async () => jsonResponse({ detail: 'Dish 99 not found' }, 404));
		const api = makeApi('http://b', 's', fetchImpl as unknown as typeof fetch);
		await expect(api.getSuggestions()).rejects.toMatchObject({ status: 404, detail: 'Dish 99 not found' } satisfies Partial<ApiError>);
	});
});
