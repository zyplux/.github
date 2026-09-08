import type { Config } from 'eslint/config';

import { zyplux } from '@zyplux/eslint-config';

const config: Config[] = [
  ...zyplux({ tsconfigRootDir: import.meta.dirname }),
  {
    rules: {
      '@zyplux/no-schemas-outside-contracts': 'off',
      'unicorn/consistent-class-member-order': 'off',
      'unicorn/default-export-style': ['error', { functions: 'separate' }],
      'unicorn/max-nested-calls': ['error', { max: 10 }],
    },
  },
  {
    files: ['tests/*/stories/*.test.ts'],
    rules: {
      '@zyplux/test-seam-only-imports': 'off',
    },
  },
  {
    files: ['tests/**/*matchers*{,/**/*}.ts'],
    rules: {
      'unicorn/no-this-outside-of-class': 'off',
    },
  },
];

export default config;
