# zyplux

This Cloudflare Worker authenticates GitHub App webhooks and refreshes the Python [review gate](../bot-review-gate).

## Review gates

PR opening, pushes and readiness changes start checks. Bot summary edits, reviews, PR-comment edits/deletions, thread resolution/reopening and Copilot check/workflow activity refresh them. The handler forwards PR numbers and head SHAs to `org_gate.yml`; that workflow owns review policy. Repository exclusions come from the [review ruleset](../../rulesets/copilot-review.json).

## Deployment

The [deployment workflow](../../.github/workflows/deploy_zyplux.yml) deploys Worker changes merged into `main` and checks `/health`. Its manual **Run workflow** button redeploys `main`. Pull requests run CI. The [custom domain](wrangler.jsonc) provides `https://github-hooks.zyplux.ai/events`; Cloudflare manages DNS and HTTPS.

| Name | Storage | Purpose |
| --- | --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | Organization variable available to all repositories | Cloudflare account hosting the Worker. |
| `CLOUDFLARE_API_TOKEN` | Organization secret available to all repositories | Account-scoped Worker deployment permission. |
| `ZYPLUX_APP_ID` | Organization variable available to `.github` | App ID from GitHub App settings. |
| `ZYPLUX_APP_PRIVATE_KEY` | Organization secret available to `.github` | Private key for short-lived installation tokens. |
| `ZYPLUX_WEBHOOK_SECRET` | `.github` production environment secret | Shared secret authenticating GitHub deliveries. |

The workflow uploads `ZYPLUX_APP_ID`, `ZYPLUX_APP_PRIVATE_KEY` and `ZYPLUX_WEBHOOK_SECRET` as Worker secret bindings. GitHub remains their authoritative store. Logs and traces are enabled in [wrangler.jsonc](wrangler.jsonc).

## GitHub App setup

The [registration contract](github-app.json) defines the App name, homepage, webhook URL, permissions and subscriptions. In **[zyplux → Settings → Developer settings → GitHub Apps](https://github.com/organizations/zyplux/settings/apps)**:

1. Set the name, homepage and webhook URL from the contract. Save a random webhook secret as `ZYPLUX_WEBHOOK_SECRET` in the production environment above and in the App settings.
2. Grant the repository permissions in the registration contract.
3. Save **App ID** as `ZYPLUX_APP_ID` with the repository access listed above.
4. Under **Credentials → Key pairs → New key**, generate a private key and save its complete PEM contents as the organization secret `ZYPLUX_APP_PRIVATE_KEY`.
5. Install the App on the organization's repositories and approve its requested permissions. The review handler applies the ruleset exclusions.
6. Run **deploy_zyplux** from `main`; check that `/health` returns `{"status":"ok"}`.

GitHub's [registration guide](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app) covers the settings. The Worker acts as the installation; no user OAuth callback is required.

## Verification and diagnosis

Open **GitHub App settings → Advanced → Recent deliveries**. Review events should receive HTTP 204 and start `org_gate` for the affected PR. Use the delivery ID to inspect Worker logs. Use **Redeliver** to retry after correcting the cause.

Run `pnpm test` and `pnpm --filter @zyplux/zyplux exec wrangler deploy --dry-run` locally. Regenerate binding types with `pnpm --filter @zyplux/zyplux run types` after changing the Worker configuration.
