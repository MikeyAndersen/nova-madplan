// @ts-check
import { defineConfig } from 'astro/config';

import cloudflare from '@astrojs/cloudflare';

// https://astro.build/config
export default defineConfig({
  output: 'server',
  // @astrojs/cloudflare v13 emulates bindings (D1 `DB`, env vars) in `astro dev`
  // automatically via Wrangler, reading wrangler.jsonc.
  adapter: cloudflare(),
});