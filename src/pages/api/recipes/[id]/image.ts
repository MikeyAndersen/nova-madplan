import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ params }) => {
	const { env } = await import('cloudflare:workers');
	const upstream = `${env.MADPLAN_API_BASE.replace(/\/$/, '')}/api/recipes/${Number(params.id)}/image`;
	const res = await fetch(upstream, { headers: { Authorization: `Bearer ${env.LIFEHUB_API_TOKEN}` } });
	if (!res.ok) return new Response(null, { status: 404 });
	return new Response(res.body, {
		status: 200,
		headers: {
			'content-type': res.headers.get('content-type') ?? 'application/octet-stream',
			'cache-control': 'private, max-age=86400',
		},
	});
};
