#!/usr/bin/env bun
import { applyOrgRulesets } from '#cli';

const RULESETS_DIR = 'rulesets';

try {
  await applyOrgRulesets(RULESETS_DIR);
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
