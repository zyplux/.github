import worker from '@zyplux/github-events';
import { createHmac, generateKeyPairSync } from 'node:crypto';
import { test as base, vi } from 'vitest';

const HEAD_SHA = '47a365c546edc2a661d47fbf5162b37f8a75ecd3';

const { privateKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  privateKeyEncoding: { format: 'pem', type: 'pkcs1' },
  publicKeyEncoding: { format: 'pem', type: 'spki' },
});

const env = { EVENTS_APP_ID: '123', EVENTS_APP_PRIVATE_KEY: privateKey, EVENTS_WEBHOOK_SECRET: 'webhook-secret' };
const envelope = {
  action: 'created',
  installation: { id: 42 },
  repository: { default_branch: 'main', name: 'zyp-vps', owner: { login: 'zyplux' } },
};

type GitHubRequest = Parameters<typeof fetch>[0];

const replyGitHub = (url: GitHubRequest) => {
  const endpoint = new Request(url).url;
  if (endpoint.endsWith('/access_tokens')) {
    return Promise.resolve(Response.json({ expires_at: '2099-01-01T00:00:00Z', token: 'installation-token' }));
  }
  if (endpoint.endsWith('/variables/CONFIG_REPOSITORY')) {
    return Promise.resolve(
      Response.json({ value: `zyplux/zyp-config-${endpoint.includes('/production/') ? 'prod' : 'staging'}` }),
    );
  }
  if (endpoint.endsWith('/variables/CONFIG_BRANCH')) {
    return Promise.resolve(Response.json({ value: 'main' }));
  }
  if (endpoint.includes('/check-suites/')) {
    return Promise.resolve(Response.json({ before: '1'.repeat(HEAD_SHA.length) }));
  }
  if (endpoint.includes('/git/trees/')) {
    const before = '1'.repeat(HEAD_SHA.length);
    const sha = (endpoint.endsWith(before) ? 'a' : 'b').repeat(HEAD_SHA.length);
    return Promise.resolve(Response.json({ tree: [{ path: 'workers', sha, type: 'tree' }] }));
  }
  if (endpoint.endsWith('/pulls')) {
    return Promise.resolve(
      Response.json([
        { head: { sha: HEAD_SHA }, number: 62, state: 'open' },
        { head: { sha: HEAD_SHA }, number: 63, state: 'closed' },
        { head: { sha: '0'.repeat(HEAD_SHA.length) }, number: 64, state: 'open' },
      ]),
    );
  }
  if (endpoint.endsWith('/pulls/62')) {
    return Promise.resolve(Response.json({ head: { sha: HEAD_SHA } }));
  }
  return Promise.resolve(new Response(undefined, { status: 204 }));
};

export const test = base
  .extend('headSha', () => HEAD_SHA)
  .extend('replyGitHub', () => replyGitHub)
  .extend('github', () => vi.spyOn(globalThis, 'fetch').mockImplementation(replyGitHub))
  .extend('configEvent', () => ({
    action: 'completed',
    repository: { ...envelope.repository, name: 'zyp-config-prod' },
    workflow_run: {
      check_suite_id: 123,
      conclusion: 'success',
      event: 'push',
      head_branch: 'main',
      head_sha: HEAD_SHA,
      name: 'ci',
      path: '.github/workflows/ci.yml',
    },
  }))
  .extend('webhook', () => ({
    fetch: (request: Request) => worker.fetch(request, env),
    send: async (event: string, body: Record<string, unknown>, signature?: string) => {
      const payload = JSON.stringify({ ...envelope, ...body });
      return worker.fetch(
        new Request('https://github-events.example/events', {
          body: payload,
          headers: {
            'content-type': 'application/json',
            'x-github-delivery': 'delivery-id',
            'x-github-event': event,
            'x-hub-signature-256':
              signature ?? `sha256=${createHmac('sha256', env.EVENTS_WEBHOOK_SECRET).update(payload).digest('hex')}`,
          },
          method: 'POST',
        }),
        env,
      );
    },
  }));

export { describe, expect } from 'vitest';
