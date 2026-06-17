import type { APIRoute } from 'astro';
import { COOKIE_NAME } from '../lib/auth';

export const GET: APIRoute = ({ cookies, redirect }) => {
  cookies.delete(COOKIE_NAME, { path: '/' });
  return redirect('/login');
};
