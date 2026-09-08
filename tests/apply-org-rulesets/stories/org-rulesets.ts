import { applyOrgRulesets } from '@zyplux/apply-org-rulesets';
import { cliTest } from '@zyplux/tests-fixtures/story';

const UPSERT_COMMAND = /^gh api --input \S+ --method (?:POST|PUT) /;

export const test = cliTest
  .extend('org', ({ shell }) => {
    shell.on(UPSERT_COMMAND, '');
    return {
      setLiveRulesets: (summaries: { id: number; name: string }[]) => {
        shell.on('gh api --paginate --slurp orgs/zyplux/rulesets', JSON.stringify(summaries.map(summary => [summary])));
      },
      upsertCommands: () => shell.commandsMatching(UPSERT_COMMAND),
    };
  })
  .extend('rulesets', ({ tempDir }) => ({
    apply: () => applyOrgRulesets(tempDir.path),
    write: async (file: string, content: string) => {
      await tempDir.write(file, content);
    },
    writeRuleset: async (file: string, name: string) => {
      await tempDir.write(file, JSON.stringify({ name }));
    },
  }));

export { describe, expect } from 'vitest';
