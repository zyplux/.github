import type { Octokit } from '@octokit/core';

import * as z from 'zod';

import { CommitSchema, ConfigEventSchema } from './contracts.ts';

const DEPLOYMENT_REPOSITORY = { owner: 'zyplux', repo: 'zyp-vps' };
const VariableSchema = z.object({ value: z.string().min(1) });
const GitRefSchema = z.object({ object: z.object({ sha: CommitSchema }) });
const CheckSuiteSchema = z.object({ before: CommitSchema.nullable() });
const TreeSchema = z.object({
  tree: z.array(z.object({ path: z.string(), sha: CommitSchema, type: z.string() })),
});

export const forwardConfig = async (body: Record<string, unknown>, github: Octokit) => {
  const parsed = ConfigEventSchema.safeParse(body);
  if (!parsed.success) return;
  const { repository, workflow_run: run } = parsed.data;
  const source = { owner: repository.owner.login, repo: repository.name };
  const targets = await Promise.all(
    ['production', 'staging'].map(async environment => {
      const [configRepository, branch] = await Promise.all(
        ['CONFIG_REPOSITORY', 'CONFIG_BRANCH'].map(async name => {
          const { data } = await github.request(
            'GET /repos/{owner}/{repo}/environments/{environment_name}/variables/{name}',
            {
              ...DEPLOYMENT_REPOSITORY,
              environment_name: environment,
              name,
            },
          );
          return VariableSchema.parse(data).value;
        }),
      );
      return { branch, environment, repository: configRepository };
    }),
  );
  const matches = targets.filter(
    target => target.repository === `${source.owner}/${source.repo}` && target.branch === run.head_branch,
  );
  const [target] = matches;
  if (target === undefined) return;
  if (matches.length !== 1) throw new Error('Config repository matches multiple deployment environments');

  const branch = await github.request('GET /repos/{owner}/{repo}/git/ref/{ref}', {
    ...source,
    ref: `heads/${target.branch}`,
  });
  if (GitRefSchema.parse(branch.data).object.sha !== run.head_sha) return;

  const { data } = await github.request('GET /repos/{owner}/{repo}/check-suites/{check_suite_id}', {
    ...source,
    check_suite_id: run.check_suite_id,
  });
  const { before } = CheckSuiteSchema.parse(data);
  const revisions = await Promise.all(
    [before, run.head_sha].map(async commit => {
      if (commit === null || /^0+$/u.test(commit)) return;
      const tree = await github.request('GET /repos/{owner}/{repo}/git/trees/{tree_sha}', {
        ...source,
        tree_sha: commit,
      });
      return TreeSchema.parse(tree.data).tree.find(entry => entry.path === 'workers' && entry.type === 'tree')?.sha;
    }),
  );
  if (revisions[0] === revisions[1]) return;
  await github.request('POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches', {
    ...DEPLOYMENT_REPOSITORY,
    inputs: {
      config_ref: run.head_sha,
      config_repository: target.repository,
      environment: target.environment,
      operation: 'workers',
      preflight: 'false',
    },
    ref: 'main',
    workflow_id: 'deploy_application.yml',
  });
  console.info(JSON.stringify({ action: 'deploy-worker-config', commit: run.head_sha, ...target }));
};
