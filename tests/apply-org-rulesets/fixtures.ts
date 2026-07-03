import type { ShellFake, TempDir } from '@zyplux/tests-fixtures';

import { applyOrgRulesets } from '@zyplux/apply-org-rulesets';
import { cliTest } from '@zyplux/tests-fixtures';

type LiveRulesetSummary = { id: number; name: string };

type Org = {
  setLiveRulesets: (summaries: LiveRulesetSummary[]) => void;
  upsertCommands: () => string[];
};

type OrgRulesetsFixtures = {
  org: Org;
  rulesets: Rulesets;
};

type Rulesets = {
  apply: () => Promise<void>;
  write: (file: string, content: string) => Promise<void>;
  writeRuleset: (file: string, name: string) => Promise<void>;
};

const UPSERT_COMMAND = /^gh api --input \S+ --method (?:POST|PUT) /;

const createOrg = (shell: ShellFake) => {
  shell.on(UPSERT_COMMAND, '');
  return {
    setLiveRulesets: summaries => {
      shell.on('gh api --paginate orgs/zyplux/rulesets', JSON.stringify(summaries));
    },
    upsertCommands: () => shell.commandsMatching(UPSERT_COMMAND),
  } satisfies Org;
};

const createRulesets = (tempDir: TempDir) =>
  ({
    apply: () => applyOrgRulesets(tempDir.path),
    write: async (file, content) => {
      await tempDir.write(file, content);
    },
    writeRuleset: async (file, name) => {
      await tempDir.write(file, JSON.stringify({ name }));
    },
  }) satisfies Rulesets;

export const test = cliTest.extend<OrgRulesetsFixtures>({
  org: async ({ shell }, use) => {
    await use(createOrg(shell));
  },
  rulesets: async ({ tempDir }, use) => {
    await use(createRulesets(tempDir));
  },
});

export { describe, expect } from 'vitest';
