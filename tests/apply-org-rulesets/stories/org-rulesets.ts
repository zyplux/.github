import { applyOrgRulesets } from '@zyplux/apply-org-rulesets';
import { chmod, copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test as base, onTestFinished, vi } from 'vitest';

const EXECUTABLE_MODE = 0o700;

export const test = base
  .extend('directory', async () => {
    const directory = await mkdtemp(path.join(tmpdir(), 'org-rulesets-'));
    onTestFinished(() => rm(directory, { force: true, recursive: true }));
    await mkdir(path.join(directory, 'config'));
    await mkdir(path.join(directory, 'bin'));
    const gh = path.join(directory, 'bin', 'gh');
    await copyFile(new URL('../doubles/gh', import.meta.url), gh);
    await chmod(gh, EXECUTABLE_MODE);
    await writeFile(path.join(directory, 'commands'), '');
    return directory;
  })
  .extend('logs', () => {
    const logs = vi.spyOn(console, 'log').mockReturnValue(undefined);
    onTestFinished(() => {
      logs.mockRestore();
    });
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
