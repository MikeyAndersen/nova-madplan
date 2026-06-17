import { describe, it, expect } from 'vitest';
import { signSession, verifySession } from '../src/lib/auth';

describe('auth', () => {
  it('verifies a token it signed with the same secret', async () => {
    const t = await signSession('mikey');
    expect(await verifySession(t, 'mikey')).toBe(true);
  });

  it('rejects a token signed with a different secret', async () => {
    const t = await signSession('mikey');
    expect(await verifySession(t, 'andet')).toBe(false);
  });

  it('rejects a tampered / malformed / missing token', async () => {
    const t = await signSession('mikey');
    expect(await verifySession(t + 'x', 'mikey')).toBe(false);
    expect(await verifySession(undefined, 'mikey')).toBe(false);
    expect(await verifySession('a.b', 'mikey')).toBe(false);
    expect(await verifySession('nodot', 'mikey')).toBe(false);
  });
});
