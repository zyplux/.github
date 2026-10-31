import * as z from 'zod';

export const JsonObjectSchema = z.record(z.string(), z.unknown());
const CommitSchema = z.string().regex(/^[\da-f]{40}$/u);
export const PullHeadSchema = z.object({ head: z.object({ sha: CommitSchema }) });
const PullSchema = z.object({ head: PullHeadSchema.shape.head.optional(), number: z.int().positive() });
const RunSchema = z.object({ head_sha: CommitSchema, name: z.string() });
export const CommitPullsSchema = z.array(
  PullSchema.extend({ head: z.object({ sha: CommitSchema }), state: z.enum(['open', 'closed']) }),
);
const EnvelopeSchema = z.object({
  action: z.string(),
  installation: z.object({ id: z.int().positive() }),
  repository: z.object({
    default_branch: z.string().min(1),
    name: z.string().regex(/^[\w.-]+$/u),
    owner: z.object({ login: z.string().min(1) }),
  }),
});

export const ReviewEventSchema = z.discriminatedUnion('event', [
  z.object({
    body: EnvelopeSchema.extend({ pull_request: PullSchema.extend({ draft: z.boolean() }) }),
    event: z.literal('pull_request'),
  }),
  z.object({
    body: EnvelopeSchema.extend({ pull_request: PullSchema }),
    event: z.enum(['pull_request_review', 'pull_request_review_comment', 'pull_request_review_thread']),
  }),
  z.object({
    body: EnvelopeSchema.extend({
      comment: z.object({ body: z.string(), user: z.object({ type: z.string() }) }),
      issue: PullSchema.extend({ pull_request: z.object({}).optional() }),
    }),
    event: z.literal('issue_comment'),
  }),
  z.object({
    body: EnvelopeSchema.extend({ check_run: RunSchema }),
    event: z.literal('check_run'),
  }),
  z.object({
    body: EnvelopeSchema.extend({
      workflow_run: RunSchema.extend({ display_title: z.string().optional() }),
    }),
    event: z.literal('workflow_run'),
  }),
]);
