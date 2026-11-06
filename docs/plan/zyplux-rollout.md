# zyplux rollout

1. In the existing `zyplux-review-events` App, approve the permissions in [github-app.json](../../apps/zyplux/github-app.json). Rename it to `zyplux`; retain its installation and webhook secret.
2. Configure the App ID, private key and webhook secret under the names and repository access in the [input table](../../apps/zyplux/README.md#deployment). Remove the superseded `REVIEW_*` environment entries after the renamed workflow succeeds.
3. Merge the service PR, deploy `zyplux` and verify `/health` and review delivery. Change the existing App's webhook URL to `https://github-hooks.zyplux.ai/events`.
4. Remove the `/review-gate` route after the App uses `/events`. Delete the unbound `zyplux-review-events` Cloudflare Worker with an explicit resource-deletion operation.
