# Review events

This Cloudflare Worker authenticates GitHub App webhooks and dispatches each affected repository's `org_gate.yml`. The Python [review gate](../bot-review-gate) evaluates the current PR head once and publishes `bot-review-complete`. Review verdicts stay in that gate; the Worker selects notifications and forwards PR numbers and head SHAs.

PR opening, pushes and readiness changes start checks. Bot summary edits, reviews, PR-comment edits/deletions, thread resolution/reopening and Copilot check/workflow activity refresh them. Unrelated CI workflows and ordinary new comments are ignored. Repository exclusions come from the [review ruleset](../../rulesets/copilot-review.json).

## Deployment

The [deployment workflow](../../.github/workflows/deploy_review_events.yml) deploys Worker changes merged into `main` and checks `/health`. Its manual **Run workflow** button redeploys `main`. Pull requests run the repository CI; deployment uses the locked Wrangler installation without rerunning CI. The custom domain in [wrangler.jsonc](wrangler.jsonc) provides `https://github-hooks.zyplux.ai/review-gate`; Cloudflare manages its DNS record and HTTPS certificate.

Configure these inputs under this repository's **Settings → Environments → production**:

| Name | Storage | Purpose |
| --- | --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | Variable | Cloudflare account hosting the Worker. |
| `CLOUDFLARE_API_TOKEN` | Secret | Account-scoped Worker deployment permission. |
| `REVIEW_APP_ID` | Variable | App ID from the GitHub App settings. |
| `REVIEW_APP_PRIVATE_KEY` | Secret | App private key; Octokit uses it to obtain short-lived installation tokens. |
| `REVIEW_WEBHOOK_SECRET` | Secret | Shared secret used to authenticate GitHub deliveries. |

The workflow uploads the three `REVIEW_*` bindings as Worker secrets. Keep their authoritative values in GitHub; subsequent deployments refresh the bindings automatically. Worker settings and logs/traces are configured in [wrangler.jsonc](wrangler.jsonc).

## GitHub App setup

Use [github-app.json](github-app.json) as the registration contract in **[zyplux → Settings → Developer settings → GitHub Apps](https://github.com/organizations/zyplux/settings/apps) → New GitHub App**:

1. Set the app name, homepage and webhook URL from the contract. Generate a random webhook secret and save the same value as `REVIEW_WEBHOOK_SECRET` in the production environment above.
2. Grant the contract's repository permissions and subscribe to its events. **Actions: Read and write** allows workflow dispatch; **Checks**, **Issues** and **Pull requests: Read-only** allow the corresponding notifications.
3. Select **Only on this account**, create the app and save its **App ID** as `REVIEW_APP_ID`.
4. Under **Credentials → Key pairs → New key**, generate a private key and save its complete PEM contents as `REVIEW_APP_PRIVATE_KEY`.
5. Run **deploy_review_events** from `main`; check that `/health` returns `{"status":"ok"}`.
6. In the app settings, select **Install App → zyplux → All repositories**. Excluded repositories are ignored according to the review ruleset.

GitHub's [registration guide](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app) covers the form. No OAuth callback or user authorization is needed: the Worker acts as the installation.

## Verification and diagnosis

Open **GitHub App settings → Advanced → Recent deliveries**. A thread resolved or reopened on an open PR should receive HTTP 204 and start `org_gate` in that repository. Check the PR's current-head `bot-review-complete` status after the run. If a delivery fails, inspect the Worker logs using its delivery ID and use **Redeliver** after correcting the cause; GitHub does not automatically retry failed webhooks.

For local verification, run `pnpm test`, `uv run pytest tests/bot-review-gate`, and `pnpm --filter @zyplux/review-events exec wrangler deploy --dry-run`. Regenerate binding types with `pnpm --filter @zyplux/review-events run types` after changing the Worker configuration.
