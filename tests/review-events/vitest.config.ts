import { defineProject } from 'vitest/config';

export default defineProject({ resolve: { tsconfigPaths: true }, test: { include: ['stories/**/*.test.ts'] } });
