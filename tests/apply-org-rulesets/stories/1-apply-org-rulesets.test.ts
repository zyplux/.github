import { describe, expect, test } from '#fixtures';

describe('1.1 discovering ruleset files', () => {
  test('1.1.1 applies every json file in name order', async ({ logs, org, rulesets }) => {
    org.setLiveRulesets([]);
    await rulesets.writeRuleset('branch-baseline.json', 'beta');
    await rulesets.writeRuleset('admin-lockdown.json', 'alpha');

    await rulesets.apply();

    expect(logs.logLines).toEqual(["created org ruleset 'alpha'", "created org ruleset 'beta'"]);
  });

  test('1.1.2 ignores files that are not json', async ({ org, rulesets }) => {
    org.setLiveRulesets([]);
    await rulesets.write('README.md', 'not a ruleset');
    await rulesets.writeRuleset('baseline.json', 'alpha');

    await rulesets.apply();

    expect(org.upsertCommands()).toHaveLength(1);
  });
});

describe('1.2 upserting each ruleset against the live org', () => {
  test('1.2.1 creates a ruleset the org does not have yet', async ({ logs, org, rulesets }) => {
    org.setLiveRulesets([{ id: 7, name: 'beta' }]);
    await rulesets.writeRuleset('baseline.json', 'alpha');

    await rulesets.apply();

    expect(org.upsertCommands()).toEqual([expect.stringMatching(/--method POST orgs\/zyplux\/rulesets$/)]);
    expect(logs.logLines).toEqual(["created org ruleset 'alpha'"]);
  });

  test('1.2.2 updates an existing ruleset through its live id', async ({ logs, org, rulesets }) => {
    org.setLiveRulesets([{ id: 42, name: 'alpha' }]);
    await rulesets.writeRuleset('baseline.json', 'alpha');

    await rulesets.apply();

    expect(org.upsertCommands()).toEqual([expect.stringMatching(/--method PUT orgs\/zyplux\/rulesets\/42$/)]);
    expect(logs.logLines).toEqual(["updated org ruleset 'alpha' (#42)"]);
  });

  test('1.2.3 matches live rulesets by declared name not by file name', async ({ logs, org, rulesets }) => {
    org.setLiveRulesets([{ id: 9, name: 'alpha' }]);
    await rulesets.writeRuleset('some-other-file-name.json', 'alpha');

    await rulesets.apply();

    expect(logs.logLines).toEqual(["updated org ruleset 'alpha' (#9)"]);
  });
});
