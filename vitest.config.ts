import { defineConfig } from 'vitest/config';

const buildConfig = () =>
  defineConfig({
    test: {
      coverage: {
        enabled: true,
        exclude: ['apps/apply-org-rulesets/src/cli.ts'],
        include: ['apps/*/src/**/*.ts'],
        provider: 'istanbul',
        thresholds: {
          branches: 90,
          functions: 90,
          lines: 90,
          statements: 90,
        },
      },
      projects: ['tests/apply-org-rulesets', 'tests/review-events'],
      restoreMocks: true,
      unstubEnvs: true,
      unstubGlobals: true,
    },
  });

export default buildConfig;
