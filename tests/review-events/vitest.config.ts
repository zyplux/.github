import { defineProject } from 'vitest/config';

const buildConfig = () =>
  defineProject({ resolve: { tsconfigPaths: true }, test: { include: ['stories/**/*.test.ts'] } });

export default buildConfig;
