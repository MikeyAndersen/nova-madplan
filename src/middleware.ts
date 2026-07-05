import { defineMiddleware } from 'astro:middleware';
import { env } from 'cloudflare:workers';
import { COOKIE_NAME, verifySession } from './lib/auth';

// Sider der altid er tilgængelige uden login.
const PUBLIC_PATHS = new Set(['/login', '/logout']);

// Statiske assets (serveres typisk af ASSETS-binding, men vi lader dem passere).
function isAsset(pathname: string): boolean {
  return pathname.startsWith('/_') || /\.[a-z0-9]+$/i.test(pathname);
}

export const onRequest = defineMiddleware(async (ctx, next) => {
  const { pathname } = new URL(ctx.request.url);

  if (PUBLIC_PATHS.has(pathname) || isAsset(pathname)) {
    return next();
  }

  const secret = env.SITE_PASSWORD;
  const token = ctx.cookies.get(COOKIE_NAME)?.value;

  if (await verifySession(token, secret)) {
    return next();
  }

  return ctx.redirect('/login');
});
