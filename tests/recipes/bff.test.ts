import { describe, it, expect, vi } from 'vitest';

describe('image proxy', () => {
	it('passes through content-type from upstream', async () => {
		vi.stubGlobal('fetch', vi.fn(async () => new Response(new Uint8Array([255, 216, 255]), {
			status: 200, headers: { 'content-type': 'image/jpeg' } })));
		vi.doMock('cloudflare:workers', () => ({ env: { MADPLAN_API_BASE: 'http://b', LIFEHUB_API_TOKEN: 't' } }));
		const { GET } = await import('../../src/pages/api/recipes/[id]/image.ts');
		const res = await GET({ params: { id: '1' } } as never);
		expect(res.status).toBe(200);
		expect(res.headers.get('content-type')).toBe('image/jpeg');
	});
});
