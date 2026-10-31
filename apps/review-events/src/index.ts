import { createAppAuth } from '@octokit/auth-app';
import { Octokit } from '@octokit/core';
import { verify } from '@octokit/webhooks-methods';
import ruleset from '@rulesets/copilot-review.json' with { type: 'json' };
import * as z from 'zod';

import { CommitPullsSchema, JsonObjectSchema, ReviewEventSchema } from './contracts.ts';

const GITHUB_TIMEOUT_MS = 8000;

const selectPulls = async ({ body, event }: z.infer<typeof ReviewEventSchema>, github: Octokit) => {
  switch (event) {
    case 'check_run':
    case 'workflow_run': {
      const run = event === 'check_run' ? body.check_run : body.workflow_run;
      if (!['copilot-pull-request-reviewer', 'Running Copilot Code Review'].includes(run.name)) return [];
      const { data } = await github.request('GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls', {
        commit_sha: run.head_sha,
        owner: body.repository.owner.login,
        repo: body.repository.name,
      });
      return CommitPullsSchema.parse(data).filter(pull => pull.state === 'open' && pull.head.sha === run.head_sha);
    }
    case 'issue_comment': {
      return body.issue.pull_request !== undefined &&
        (body.comment.user.type === 'Bot' || /@codex\s+review\b/iu.test(body.comment.body))
        ? [body.issue]
        : [];
    }
    case 'pull_request': {
      return !body.pull_request.draft && ['opened', 'ready_for_review', 'reopened', 'synchronize'].includes(body.action)
        ? [body.pull_request]
        : [];
    }
    default: {
      return [body.pull_request];
    }
  }
};

const forwardReview = async (
  request: Request,
  { REVIEW_APP_ID: appId, REVIEW_APP_PRIVATE_KEY: privateKey, REVIEW_WEBHOOK_SECRET: webhookSecret }: Env,
) => {
  const payload = await request.text();
  const signature = request.headers.get('x-hub-signature-256');
  if (signature === null || !(await verify(webhookSecret, payload, signature))) {
    return new Response('Invalid webhook signature', { status: 401 });
  }
  const event = request.headers.get('x-github-event');
  if (event === 'ping' || event === 'installation' || event === 'installation_repositories') {
    return new Response(undefined, { status: 204 });
  }
  const parsed = ReviewEventSchema.safeParse({ body: JsonObjectSchema.parse(JSON.parse(payload)), event });
  if (!parsed.success) return new Response('Invalid review event', { status: 400 });
  const { installation, repository } = parsed.data.body;
  if (repository.owner.login !== 'zyplux' || ruleset.conditions.repository_name.exclude.includes(repository.name)) {
    return new Response(undefined, { status: 204 });
  }
  const github = new Octokit({
    auth: { appId, installationId: installation.id, privateKey },
    authStrategy: createAppAuth,
    request: { signal: AbortSignal.timeout(GITHUB_TIMEOUT_MS) },
  });
  const pulls = await selectPulls(parsed.data, github);
  for (const pull of pulls) {
    await github.request('POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches', {
      inputs: { pr: String(pull.number) },
      owner: repository.owner.login,
      ref: repository.default_branch,
      repo: repository.name,
      workflow_id: 'org_gate.yml',
    });
    console.info(
      JSON.stringify({
        delivery: request.headers.get('x-github-delivery'),
        event,
        pr: pull.number,
        repository: repository.name,
      }),
    );
  }
  return new Response(undefined, { status: 204 });
};

const worker = {
  fetch: async (request: Request, env) => {
    const pathname = new URL(request.url).pathname;
    if (pathname === '/health' && request.method === 'GET') return Response.json({ status: 'ok' });
    if (pathname !== '/review-gate' || request.method !== 'POST') return new Response(undefined, { status: 404 });
    try {
      return await forwardReview(request, env);
    } catch (error) {
      console.error(
        JSON.stringify({
          delivery: request.headers.get('x-github-delivery'),
          error: error instanceof Error ? error.message : String(error),
        }),
      );
      return new Response('Review dispatch failed', { status: 502 });
    }
  },
} satisfies ExportedHandler<Env>;

export default worker;
