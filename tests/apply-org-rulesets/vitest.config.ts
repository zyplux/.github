import { defineProject } from 'vitest/config';

export default defineProject({
  test: {
    include: ['stories/**/*.test.ts'],
    server: {
      deps: {
        inline: ['@zyplux/tests-fixtures', '@zyplux/util'],
      },
    },
    setupFiles: ['../vitest.setup.ts'],
  },
});
