import { defineProject } from 'vitest/config';

const buildConfig = () =>
  defineProject({
    test: {
      include: ['stories/**/*.test.ts'],
    },
  });

export default buildConfig;
