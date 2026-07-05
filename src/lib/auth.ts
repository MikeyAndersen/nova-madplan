// Delt-password gate: en signeret session-cookie.
// Hemmeligheden ER selve passwordet (SITE_PASSWORD). Cookien indeholder ingen
// brugerdata — kun et statisk payload + HMAC, så den ikke kan forfalskes uden
// at kende passwordet.

export const COOKIE_NAME = 'madplan_session';
export const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 dage i sekunder

const PAYLOAD = 'ok';

async function hmacHex(message: string, secret: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Lav en sessionstoken på formen "<payload>.<hmacHex>". */
export async function signSession(secret: string): Promise<string> {
  return `${PAYLOAD}.${await hmacHex(PAYLOAD, secret)}`;
}

/** Verificér at en token er signeret med samme secret. Konstant-tids-ish sammenligning. */
export async function verifySession(
  token: string | undefined,
  secret: string,
): Promise<boolean> {
  if (!token) return false;
  const dot = token.lastIndexOf('.');
  if (dot <= 0) return false;
  const payload = token.slice(0, dot);
  const got = token.slice(dot + 1);
  const expected = await hmacHex(payload, secret);
  if (got.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < got.length; i++) {
    diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}
