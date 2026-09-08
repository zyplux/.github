import { $, parseJson, readJson, readTrimmed } from '@zyplux/util';
import { readdir } from 'node:fs/promises';
import path from 'node:path';

import { RulesetFileSchema, RulesetPagesSchema } from './contracts.ts';

const ORG = 'zyplux';

const listOrgRulesets = async () =>
  parseJson(
    await readTrimmed($.gh.api(`orgs/${ORG}/rulesets`, { paginate: true, slurp: true })),
    RulesetPagesSchema,
  ).flat();

export const applyOrgRulesets = async (rulesetsDir: string) => {
  const entries = await readdir(rulesetsDir);
  const files = entries.filter(name => name.endsWith('.json')).toSorted((a, b) => a.localeCompare(b));
  const live = await listOrgRulesets();

  for (const file of files) {
    const filePath = path.join(rulesetsDir, file);
    const { name } = await readJson(filePath, RulesetFileSchema);
    const match = live.find(ruleset => ruleset.name === name);

    if (match === undefined) {
      await $.gh.api(`orgs/${ORG}/rulesets`, { input: filePath, method: 'POST' });
      console.log(`created org ruleset '${name}'`);
    } else {
      await $.gh.api(`orgs/${ORG}/rulesets/${match.id}`, { input: filePath, method: 'PUT' });
      console.log(`updated org ruleset '${name}' (#${match.id})`);
    }
  }
};
