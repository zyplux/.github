import { describe, expect, test } from './stories.ts';

describe('1.1 authenticating webhook deliveries', () => {
  test('1.1.1 rejects forged deliveries before contacting GitHub', async ({ github, webhook }) => {
    const response = await webhook.send('pull_request_review_thread', { pull_request: { number: 62 } }, 'sha256=bad');

    expect(response).toMatchObject({ status: 401 });
    expect(github).not.toHaveBeenCalled();
  });

  test('1.1.2 rejects malformed signed events', async ({ github, webhook }) => {
    const response = await webhook.send('pull_request_review_thread', {});

    expect(response).toMatchObject({ status: 400 });
    expect(github).not.toHaveBeenCalled();
  });

  test('1.1.3 ignores repositories outside the organisation', async ({ github, webhook }) => {
    const response = await webhook.send('pull_request_review_thread', {
      pull_request: { number: 62 },
      repository: { default_branch: 'main', name: 'zyp-vps', owner: { login: 'unrelated' } },
    });

    expect(response).toMatchObject({ status: 204 });
    expect(github).not.toHaveBeenCalled();
  });

  test('1.1.4 respects the review ruleset exclusions', async ({ github, webhook }) => {
    const response = await webhook.send('pull_request_review_thread', {
      pull_request: { number: 62 },
      repository: { default_branch: 'main', name: 'zyp-vps-configs', owner: { login: 'zyplux' } },
    });

    expect(response).toMatchObject({ status: 204 });
    expect(github).not.toHaveBeenCalled();
  });
});

describe('1.2 refreshing the aggregate review gate', () => {
  test.for(['resolved', 'unresolved'])(
    '1.2.1 refreshes thread resolution and reopening (%s)',
    async (action, { github, headSha, webhook }) => {
      const response = await webhook.send('pull_request_review_thread', { action, pull_request: { number: 62 } });

      expect(response).toMatchObject({ status: 204 });
      const dispatch = github.mock.calls.find(([url]) => new Request(url).url.endsWith('/dispatches'));
      expect(dispatch).toEqual([
        'https://api.github.com/repos/zyplux/zyp-vps/actions/workflows/org_gate.yml/dispatches',
        expect.objectContaining({
          body: JSON.stringify({ inputs: { pr: '62', sha: headSha }, ref: 'main' }),
          method: 'POST',
        }),
      ]);
    },
  );

  test.for(['pull_request_review', 'pull_request_review_comment'])(
    '1.2.2 refreshes posted and edited reviews (%s)',
    async (event, { github, webhook }) => {
      await expect(webhook.send(event, { pull_request: { number: 62 } })).resolves.toMatchObject({ status: 204 });
      expect(github).toHaveBeenCalledWith(expect.stringContaining('/dispatches'), expect.anything());
    },
  );

  test('1.2.3 refreshes ready pull requests', async ({ github, webhook }) => {
    await expect(
      webhook.send('pull_request', {
        action: 'ready_for_review',
        pull_request: { draft: false, number: 62 },
      }),
    ).resolves.toMatchObject({ status: 204 });
    expect(github).toHaveBeenCalledWith(expect.stringContaining('/dispatches'), expect.anything());
  });

  test('1.2.4 refreshes bot summary edits and explicit review requests', async ({ github, webhook }) => {
    const comments = [
      { body: 'Review complete', user: { type: 'Bot' } },
      { body: '@codex review', user: { type: 'User' } },
    ];
    for (const comment of comments) {
      await expect(
        webhook.send('issue_comment', {
          comment,
          issue: { number: 62, pull_request: {} },
        }),
      ).resolves.toMatchObject({ status: 204 });
    }
    expect(github.mock.calls.filter(([url]) => new Request(url).url.endsWith('/dispatches'))).toHaveLength(
      comments.length,
    );
  });

  test('1.2.5 refreshes Copilot check activity', async ({ github, headSha, webhook }) => {
    await expect(
      webhook.send('check_run', {
        check_run: { head_sha: headSha, name: 'copilot-pull-request-reviewer', pull_requests: [] },
      }),
    ).resolves.toMatchObject({ status: 204 });
    const dispatches = github.mock.calls.filter(([url]) => new Request(url).url.endsWith('/dispatches'));
    expect(dispatches).toHaveLength(1);
    expect(dispatches[0]?.[1]?.body).toBe(JSON.stringify({ inputs: { pr: '62', sha: headSha }, ref: 'main' }));
  });

  test('1.2.6 refreshes a later Copilot workflow start', async ({ github, headSha, webhook }) => {
    await expect(
      webhook.send('workflow_run', {
        action: 'in_progress',
        workflow_run: {
          display_title: 'Running Copilot Code Review',
          head_sha: headSha,
          name: 'Copilot',
          pull_requests: [],
        },
      }),
    ).resolves.toMatchObject({ status: 204 });
    expect(github).toHaveBeenCalledWith(expect.stringContaining('/dispatches'), expect.anything());
  });

  test('1.2.7 exposes dispatch failures for investigation', async ({ github, webhook }) => {
    github.mockResolvedValue(new Response('Unavailable', { status: 503 }));

    await expect(webhook.send('pull_request_review_thread', { pull_request: { number: 62 } })).resolves.toMatchObject({
      status: 502,
    });
  });

  test.for(['edited', 'deleted'])(
    '1.2.8 refreshes removed review requests (%s)',
    async (action, { github, webhook }) => {
      await expect(
        webhook.send('issue_comment', {
          action,
          comment: { body: 'request withdrawn', user: { type: 'User' } },
          issue: { number: 62, pull_request: {} },
        }),
      ).resolves.toMatchObject({ status: 204 });
      expect(github).toHaveBeenCalledWith(expect.stringContaining('/dispatches'), expect.anything());
    },
  );

  test('1.2.9 forwards the webhook head without fetching the pull request', async ({ github, headSha, webhook }) => {
    await expect(
      webhook.send('pull_request_review_thread', {
        action: 'resolved',
        pull_request: { head: { sha: headSha }, number: 62 },
      }),
    ).resolves.toMatchObject({ status: 204 });
    expect(github.mock.calls.some(([url]) => new Request(url).url.endsWith('/pulls/62'))).toBe(false);
    expect(github.mock.calls.find(([url]) => new Request(url).url.endsWith('/dispatches'))?.[1]?.body).toBe(
      JSON.stringify({ inputs: { pr: '62', sha: headSha }, ref: 'main' }),
    );
  });
});

describe('1.3 ignoring unrelated activity', () => {
  test.for([
    ['pull_request', { action: 'opened', pull_request: { draft: true, number: 62 } }],
    ['pull_request', { action: 'labeled', pull_request: { draft: false, number: 62 } }],
    ['issue_comment', { comment: { body: 'hello', user: { type: 'User' } }, issue: { number: 62, pull_request: {} } }],
    ['issue_comment', { comment: { body: '@codex review', user: { type: 'Bot' } }, issue: { number: 62 } }],
    ['ping', {}],
  ] as const)(
    '1.3.1 acknowledges irrelevant events without dispatching (%s)',
    async ([event, body], { github, webhook }) => {
      await expect(webhook.send(event, body)).resolves.toMatchObject({ status: 204 });
      expect(github).not.toHaveBeenCalled();
    },
  );

  test('1.3.2 exposes health without accepting other routes', async ({ github, webhook }) => {
    await expect(webhook.fetch(new Request('https://review-events.example/health'))).resolves.toMatchObject({
      status: 200,
    });
    await expect(webhook.fetch(new Request('https://review-events.example/'))).resolves.toMatchObject({ status: 404 });
    expect(github).not.toHaveBeenCalled();
  });

  test.for(['check_run', 'workflow_run'])(
    '1.3.3 ignores unrelated checks and workflows (%s)',
    async (event, { github, headSha, webhook }) => {
      await expect(webhook.send(event, { [event]: { head_sha: headSha, name: 'ci' } })).resolves.toMatchObject({
        status: 204,
      });
      expect(github).not.toHaveBeenCalled();
    },
  );
});
