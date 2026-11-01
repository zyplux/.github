# GitHub events

This Cloudflare Worker authenticates GitHub App webhooks and starts trusted GitHub workflows. Its review handler refreshes the Python [review gate](../bot-review-gate); its config handler starts Worker updates in `zyp-vps`. GitHub Actions performs deployment using the selected environment's credentials.

## Review gates

PR opening, pushes and readiness changes start checks. Bot summary edits, reviews, PR-comment edits/deletions, thread resolution/reopening and Copilot check/workflow activity refresh them. The handler forwards PR numbers and head SHAs to `org_gate.yml`; that workflow owns review policy. Repository exclusions come from the [review ruleset](../../rulesets/copilot-review.json).

## Worker config updates

Successful push runs of `.github/workflows/ci.yml` can trigger Worker updates. The handler reads `CONFIG_REPOSITORY` and `CONFIG_BRANCH` from `zyp-vps`'s production and staging GitHub Environments and matches the source repository and branch. It skips superseded commits and compares the `workers/` Git tree before and after the push, covering every commit in that push.

A changed tree starts `zyp-vps`'s `deploy_application.yml` on `main` with operation `workers`, the matching environment and the validated config commit. Other config changes start no deployment. Config repositories need no dispatch credential. The handler fixes the target workflow and operation; webhook contents cannot select VPS maintenance operations.

## Deployment

The [deployment workflow](../../.github/workflows/deploy_github_events.yml) deploys Worker changes merged into `main` and checks `/health`. Its manual **Run workflow** button redeploys `main`. Pull requests run CI. The [custom domain](wrangler.jsonc) provides `https://github-hooks.zyplux.ai/events`; Cloudflare manages DNS and HTTPS.

| Name | Storage | Purpose |
| --- | --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | `.github` production environment variable | Cloudflare account hosting the Worker. |
| `CLOUDFLARE_API_TOKEN` | `.github` production environment secret | Account-scoped Worker deployment permission. |
| `EVENTS_APP_ID` | Organization variable available to `.github` | App ID from GitHub App settings. |
| `EVENTS_APP_CLIENT_ID` | Organization variable available to `zyp-vps` | Client ID for creating read-only config-access tokens. |
| `EVENTS_APP_PRIVATE_KEY` | Organization secret restricted to `.github` and `zyp-vps` | Private key for short-lived installation tokens. |
| `EVENTS_WEBHOOK_SECRET` | `.github` production environment secret | Shared secret authenticating GitHub deliveries. |

The workflow uploads `EVENTS_APP_ID`, `EVENTS_APP_PRIVATE_KEY` and `EVENTS_WEBHOOK_SECRET` as Worker secret bindings. GitHub remains their authoritative store. Logs and traces are enabled in [wrangler.jsonc](wrangler.jsonc).

## GitHub App setup

Use one App for these event handlers. Its [registration contract](github-app.json) defines the name, homepage, webhook URL, permissions and subscriptions. In **[zyplux → Settings → Developer settings → GitHub Apps](https://github.com/organizations/zyplux/settings/apps)**:

1. Set the name, homepage and webhook URL from the contract. Save a random webhook secret as `EVENTS_WEBHOOK_SECRET` in the production environment above and in the App settings.
2. Grant the contract's repository permissions: **Actions: Read and write** for workflow events and dispatch; **Checks**, **Issues** and **Pull requests: Read-only** for review notifications; **Contents: Read-only** for config trees and private config reads; **Environments: Read-only** for deployment selectors.
3. Save **App ID** as `EVENTS_APP_ID` and **Client ID** as `EVENTS_APP_CLIENT_ID` with the repository access listed above.
4. Under **Credentials → Key pairs → New key**, generate a private key and save its complete PEM contents as the organization secret `EVENTS_APP_PRIVATE_KEY`.
5. Install the App on the organization's repositories and approve its requested permissions. The review handler applies the ruleset exclusions; the config handler accepts only repositories and branches selected by `zyp-vps`'s GitHub Environments.
6. Run **deploy_github_events** from `main`; check that `/health` returns `{"status":"ok"}`.

GitHub's [registration guide](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app) covers the settings. The Worker acts as the installation; no user OAuth callback is required.

## Verification and diagnosis

Open **GitHub App settings → Advanced → Recent deliveries**. Review events should receive HTTP 204 and start `org_gate` for the affected PR. A successful config CI run with changed `workers/` should start the matching environment's Worker update. Inspect structured Worker logs using the delivery ID. GitHub does not automatically retry failed webhooks; use **Redeliver** after correcting the cause.

Run `pnpm test` and `pnpm --filter @zyplux/github-events exec wrangler deploy --dry-run` locally. Regenerate binding types with `pnpm --filter @zyplux/github-events run types` after changing the Worker configuration.
