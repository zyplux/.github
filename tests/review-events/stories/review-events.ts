import worker from '@zyplux/review-events';
import { createHmac, generateKeyPairSync } from 'node:crypto';
import { test as base, vi } from 'vitest';

export const HEAD_SHA = '47a365c546edc2a661d47fbf5162b37f8a75ecd3';

const { privateKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  privateKeyEncoding: { format: 'pem', type: 'pkcs1' },
  publicKeyEncoding: { format: 'pem', type: 'spki' },
});

const env = { REVIEW_APP_ID: '123', REVIEW_APP_PRIVATE_KEY: privateKey, REVIEW_WEBHOOK_SECRET: 'webhook-secret' };
const envelope = {
  action: 'created',
  installation: { id: 42 },
  repository: { default_branch: 'main', name: 'zyp-vps', owner: { login: 'zyplux' } },
};

export const test = base
  .extend('github', () =>
    vi.spyOn(globalThis, 'fetch').mockImplementation(url => {
      const endpoint = new Request(url).url;
      if (endpoint.endsWith('/access_tokens')) {
        return Promise.resolve(Response.json({ expires_at: '2099-01-01T00:00:00Z', token: 'installation-token' }));
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
      return Promise.resolve(new Response(undefined, { status: 204 }));
    }),
  )
  .extend('webhook', () => ({
    fetch: (request: Request) => worker.fetch(request, env),
    send: async (event: string, body: Record<string, unknown>, signature?: string) => {
      const payload = JSON.stringify({ ...envelope, ...body });
      return worker.fetch(
        new Request('https://review-events.example/review-gate', {
          body: payload,
          headers: {
            'content-type': 'application/json',
            'x-github-delivery': 'delivery-id',
            'x-github-event': event,
            'x-hub-signature-256':
              signature ?? `sha256=${createHmac('sha256', env.REVIEW_WEBHOOK_SECRET).update(payload).digest('hex')}`,
          },
          method: 'POST',
        }),
        env,
      );
    },
  }));

export { describe, expect } from 'vitest';
