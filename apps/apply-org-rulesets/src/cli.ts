import { $, parseJson, readJson, readTrimmed } from '@zyplux/util';
import { readdir } from 'node:fs/promises';
import path from 'node:path';
import * as z from 'zod';

const ORG = 'zyplux';

const RulesetSummariesSchema = z.array(z.object({ id: z.number(), name: z.string() }));
const RulesetFileSchema = z.object({ name: z.string() });

const listOrgRulesets = async () =>
  parseJson(await readTrimmed($.gh.api(`orgs/${ORG}/rulesets`, { paginate: true })), RulesetSummariesSchema);

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
