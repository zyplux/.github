# GitHub event service rollout

1. In the existing `zyplux-review-events` App, approve the permissions in [github-app.json](../../apps/github-events/github-app.json). Rename it to `zyplux-github-events`; retain its installation and webhook secret.
2. Configure the existing App's IDs, private key and webhook secret under the names and repository access in the [input table](../../apps/github-events/README.md#deployment). Remove the superseded `REVIEW_*` environment entries after the renamed workflow succeeds.
3. Merge the service PR, deploy `zyplux-github-events` and verify `/health` and review delivery. Change the existing App's webhook URL to `https://github-hooks.zyplux.ai/events`.
4. Verify a successful config CI event starts only the matching environment's Worker update. Application activation still follows the Phase 4 staging readiness checks.
5. Remove the `/review-gate` route after the App uses `/events`. Delete the unbound `zyplux-review-events` Cloudflare Worker with an explicit resource-deletion operation.
