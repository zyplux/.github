import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      enabled: true,
      exclude: ['apps/apply-org-rulesets/src/index.ts'],
      include: ['apps/apply-org-rulesets/src/**'],
      provider: 'istanbul',
      thresholds: {
        branches: 90,
        functions: 90,
        lines: 90,
        statements: 90,
      },
    },
    projects: ['tests/apply-org-rulesets'],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
});
