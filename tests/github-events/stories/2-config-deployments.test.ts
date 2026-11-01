import { describe, expect, test } from './stories.ts';

describe('2.1 dispatching Worker config updates', () => {
  test.for(['prod', 'staging'])(
    '2.1.1 selects the environment from its configured repository (%s)',
    async (suffix, { configEvent, github, headSha, webhook }) => {
      const repository = { ...configEvent.repository, name: `zyp-config-${suffix}` };
      await expect(webhook.send('workflow_run', { ...configEvent, repository })).resolves.toMatchObject({
        status: 204,
      });

      const dispatches = github.mock.calls.filter(([url]) => new Request(url).url.endsWith('/dispatches'));
      expect(dispatches).toEqual([
        [
          'https://api.github.com/repos/zyplux/zyp-vps/actions/workflows/deploy_application.yml/dispatches',
          expect.objectContaining({
            body: JSON.stringify({
              inputs: {
                config_ref: headSha,
                config_repository: `zyplux/${repository.name}`,
                environment: suffix === 'prod' ? 'production' : 'staging',
                operation: 'workers',
                preflight: 'false',
              },
              ref: 'main',
            }),
            method: 'POST',
          }),
        ],
      ]);
      expect(
        github.mock.calls.some(([url]) => new Request(url).url.endsWith(`/git/trees/${'1'.repeat(headSha.length)}`)),
      ).toBe(true);
    },
  );

  test('2.1.2 skips updates when the workers directory is unchanged', async ({
    configEvent,
    github,
    headSha,
    replyGitHub,
    webhook,
  }) => {
    github.mockImplementation(url =>
      new Request(url).url.includes('/git/trees/')
        ? Promise.resolve(Response.json({ tree: [{ path: 'workers', sha: 'a'.repeat(headSha.length), type: 'tree' }] }))
        : replyGitHub(url),
    );

    await expect(webhook.send('workflow_run', configEvent)).resolves.toMatchObject({ status: 204 });
    expect(github.mock.calls.some(([url]) => new Request(url).url.endsWith('/dispatches'))).toBe(false);
  });

  test('2.1.3 handles an initial push without a previous tree', async ({
    configEvent,
    github,
    headSha,
    replyGitHub,
    webhook,
  }) => {
    github.mockImplementation(url =>
      new Request(url).url.includes('/check-suites/')
        ? Promise.resolve(Response.json({ before: '0'.repeat(headSha.length) }))
        : replyGitHub(url),
    );

    await expect(webhook.send('workflow_run', configEvent)).resolves.toMatchObject({ status: 204 });
    expect(github.mock.calls.filter(([url]) => new Request(url).url.includes('/git/trees/'))).toHaveLength(1);
    expect(github.mock.calls.some(([url]) => new Request(url).url.endsWith('/dispatches'))).toBe(true);
  });
});

describe('2.2 restricting deployment authority', () => {
  test.for([
    { conclusion: 'failure' },
    { event: 'pull_request' },
    { head_branch: 'feature' },
    { path: '.github/workflows/other.yml' },
  ])(
    '2.2.1 ignores unsuccessful CI and unconfigured sources (%j)',
    async (override, { configEvent, github, webhook }) => {
      await expect(
        webhook.send('workflow_run', { ...configEvent, workflow_run: { ...configEvent.workflow_run, ...override } }),
      ).resolves.toMatchObject({ status: 204 });
      expect(github.mock.calls.some(([url]) => new Request(url).url.endsWith('/dispatches'))).toBe(false);
    },
  );

  test('2.2.2 ignores repositories absent from the environment selectors', async ({ configEvent, github, webhook }) => {
    await expect(
      webhook.send('workflow_run', { ...configEvent, repository: { ...configEvent.repository, name: 'other-config' } }),
    ).resolves.toMatchObject({ status: 204 });
    expect(github.mock.calls.some(([url]) => new Request(url).url.endsWith('/dispatches'))).toBe(false);
  });

  test('2.2.3 refuses an ambiguous environment selector', async ({ configEvent, github, replyGitHub, webhook }) => {
    github.mockImplementation(url =>
      new Request(url).url.endsWith('/variables/CONFIG_REPOSITORY')
        ? Promise.resolve(Response.json({ value: 'zyplux/zyp-config-prod' }))
        : replyGitHub(url),
    );

    await expect(webhook.send('workflow_run', configEvent)).resolves.toMatchObject({ status: 502 });
    expect(github.mock.calls.some(([url]) => new Request(url).url.endsWith('/dispatches'))).toBe(false);
  });
});
