import worker from '@zyplux/zyplux';
import { createHmac, generateKeyPairSync } from 'node:crypto';
import { test as base, vi } from 'vitest';

const HEAD_SHA = '47a365c546edc2a661d47fbf5162b37f8a75ecd3';

const { privateKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  privateKeyEncoding: { format: 'pem', type: 'pkcs1' },
  publicKeyEncoding: { format: 'pem', type: 'spki' },
});

const env = {
  ZYPLUX_APP_ID: '123',
  ZYPLUX_APP_PRIVATE_KEY: { get: () => Promise.resolve(privateKey) },
  ZYPLUX_WEBHOOK_SECRET: 'webhook-secret',
};
const envelope = {
  action: 'created',
  installation: { id: 42 },
  repository: { default_branch: 'main', name: 'zyp-vps', owner: { login: 'zyplux' } },
};

type GitHubRequest = Parameters<typeof fetch>[0];

const replyReview = (endpoint: string) => {
  if (endpoint.endsWith('/pulls')) {
    return Response.json([
      { head: { sha: HEAD_SHA }, number: 62, state: 'open' },
      { head: { sha: HEAD_SHA }, number: 63, state: 'closed' },
      { head: { sha: '0'.repeat(HEAD_SHA.length) }, number: 64, state: 'open' },
    ]);
  }
  return endpoint.endsWith('/pulls/62') ? Response.json({ head: { sha: HEAD_SHA } }) : undefined;
};

const replyGitHub = (url: GitHubRequest) => {
  const endpoint = new Request(url).url;
  return Promise.resolve(
    endpoint.endsWith('/access_tokens')
      ? Response.json({ expires_at: '2099-01-01T00:00:00Z', token: 'installation-token' })
      : (replyReview(endpoint) ?? new Response(undefined, { status: 204 })),
  );
};

export const test = base
  .extend('headSha', () => HEAD_SHA)
  .extend('github', () => vi.spyOn(globalThis, 'fetch').mockImplementation(replyGitHub))
  .extend('webhook', () => ({
    fetch: (request: Request) => worker.fetch(request, env),
    send: async (event: string, body: Record<string, unknown>, signature?: string) => {
      const payload = JSON.stringify({ ...envelope, ...body });
      return worker.fetch(
        new Request('https://zyplux.example/events', {
          body: payload,
          headers: {
            'content-type': 'application/json',
            'x-github-delivery': 'delivery-id',
            'x-github-event': event,
            'x-hub-signature-256':
              signature ?? `sha256=${createHmac('sha256', env.ZYPLUX_WEBHOOK_SECRET).update(payload).digest('hex')}`,
          },
          method: 'POST',
        }),
        env,
      );
    },
  }));

export { describe, expect } from 'vitest';
