import { defineConfig } from 'vitest/config';

// Test config. We rely on esbuild's automatic JSX transform rather than the
// full React Babel plugin: it is faster and avoids a Vitest 2.x collection
// issue ("failed to find the current suite") seen with the plugin on this
// environment. A single fork keeps runs deterministic on slow filesystems.
export default defineConfig({
  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    pool: 'forks',
    poolOptions: { forks: { singleFork: true } },
  },
});
