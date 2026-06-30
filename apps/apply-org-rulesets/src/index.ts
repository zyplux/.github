#!/usr/bin/env bun
import { parseJson, readJson } from '@zyplux/util';
import { $, readTrimmed } from '@zyplux/util/shell';
import { readdir } from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';

const ORG = 'zyplux';
const RULESETS_DIR = 'rulesets';

const RulesetSummariesSchema = z.array(z.object({ id: z.number(), name: z.string() }));
const RulesetFileSchema = z.object({ name: z.string() });

const listOrgRulesets = async () =>
  parseJson(await readTrimmed($.gh.api(`orgs/${ORG}/rulesets`, { paginate: true })), RulesetSummariesSchema);

const applyOrgRulesets = async () => {
  const entries = await readdir(RULESETS_DIR);
  const files = entries.filter(name => name.endsWith('.json')).toSorted((a, b) => a.localeCompare(b));
  const live = await listOrgRulesets();

  for (const file of files) {
    const filePath = path.join(RULESETS_DIR, file);
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

try {
  await applyOrgRulesets();
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
