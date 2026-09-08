import { applyOrgRulesets } from '@zyplux/apply-org-rulesets';
import { copyFile, chmod, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { onTestFinished, test as base, vi } from 'vitest';

export const test = base
  .extend('directory', async () => {
    const directory = await mkdtemp(path.join(tmpdir(), 'org-rulesets-'));
    onTestFinished(() => rm(directory, { recursive: true, force: true }));
    await mkdir(path.join(directory, 'config'));
    await mkdir(path.join(directory, 'bin'));
    const gh = path.join(directory, 'bin', 'gh');
    await copyFile(new URL('../doubles/gh', import.meta.url), gh);
    await chmod(gh, 0o700);
    await writeFile(path.join(directory, 'commands'), '');
    return directory;
  })
  .extend('logs', () => {
    const logs = vi.spyOn(console, 'log').mockImplementation(() => {});
    onTestFinished(() => logs.mockRestore());
    return logs;
  })
  .extend('org', ({ directory }) => {
    vi.stubEnv('PATH', `${path.join(directory, 'bin')}${path.delimiter}${process.env['PATH'] ?? ''}`);
    vi.stubEnv('RULESET_PAGES', path.join(directory, 'pages'));
    vi.stubEnv('RULESET_COMMANDS', path.join(directory, 'commands'));
    onTestFinished(() => {
      vi.unstubAllEnvs();
    });
    return {
      setLiveRulesets: (summaries: { id: number; name: string }[]) =>
        writeFile(path.join(directory, 'pages'), JSON.stringify(summaries.map(summary => [summary]))),
      upsertCommands: async () => {
        const commands = await readFile(path.join(directory, 'commands'), 'utf8');
        return commands.split('\n').filter(Boolean);
      },
    };
  })
  .extend('rulesets', ({ directory }) => ({
    apply: () => applyOrgRulesets(path.join(directory, 'config')),
    write: (file: string, content: string) => writeFile(path.join(directory, 'config', file), content),
    writeRuleset: (file: string, name: string) =>
      writeFile(path.join(directory, 'config', file), JSON.stringify({ name })),
  }));

export { describe, expect } from 'vitest';
