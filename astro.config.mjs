// @ts-check
import { defineConfig } from 'astro/config';

import cloudflare from '@astrojs/cloudflare';

// https://astro.build/config
export default defineConfig({
  output: 'server',
  adapter: cloudflare({
    // Exposes Cloudflare bindings (D1 `DB`, env vars) to `astro dev` locally
    platformProxy: { enabled: true },
  }),
});