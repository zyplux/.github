# Bot review gate

The reusable [org gate](../../.github/workflows/org_gate_base.yml) publishes the required `bot-review-complete` commit status for Copilot and Codex Code Review and Security Review.

| Copilot | Codex | Gate |
|---|---|---|
| Clean | Clean | Success |
| Explicit quota denial | Clean | Success |
| Clean | Explicit quota denial | Success |
| Unresolved findings | Any | Failure |
| Any | Unresolved findings | Failure |
| No review detected | Clean | Success |
| Clean | No review detected | Success |
| No review detected | No review detected | Pending |
| Review in progress | Clean or no review detected | Pending |
| Clean or no review detected | Review in progress | Pending |
| Explicit quota denial | Explicit quota denial | Failure |

At least one bot must complete a clean review of the current PR head. Only bots that have started reviewing that commit participate; queued Copilot requests alone do not block. Copilot must have a successful check-run and a submitted review. Codex must have completed `code_review` and `security_review` entries for that commit in its bot-authored `codex-review-state:v1` summary. A missing, queued or running Codex review keeps the gate pending, even when the other review or Copilot is clean. Either Codex review failing or being cancelled makes the gate fail. Live GitHub review threads determine whether findings remain unresolved; summary resolution flags can be stale, and Security Review can report null finding flags after completion. The gate also checks unresolved threads from both bots, including threads on earlier commits.

Only explicit quota-denial responses from the known bot accounts count as unavailable. API errors, failed checks, cancellations, and timeouts block the gate. Copilot's quota review must cover the current head; a newer check-run invalidates an earlier quota denial. Codex's quota response must have current-head context in its Code Review summary or submitted review. A newer review request or review activity supersedes the response.

## Running the gate

[bot_review_complete.py](src/bot_review_gate/bot_review_complete.py) reads `REPO`, `PR`, `GH_TOKEN`, and optional `SHA`. The workflow token needs `checks: read`, `pull-requests: read`, and `statuses: write`. When `SHA` is omitted, the check evaluates the live head. Draft and closed PRs, and superseded heads, are skipped.

Each run reads the current review state, publishes one verdict and exits. Reviews, issue comments, check-runs and review threads are paginated. Pending reviews leave a blocking `pending` status; the runner finishes immediately. Exit code zero means evaluation completed, while the commit status carries the merge verdict. API failures publish `error` and exit with code one.

The [review event Worker](../review-events) dispatches `org_gate` on PR, review, summary and thread-resolution activity. A later review from the second bot triggers a fresh evaluation and can invalidate success. The workflow runs its trusted default-branch definition; the gate never checks out PR code. Manual `org_gate` dispatch with a PR number is available for diagnosis or webhook redelivery recovery.

## Rollout

Merge the shared workflow and script before applying the version-controlled org rulesets with `just apply-org-ruleset`. The `copilot-review` ruleset requests automatic Copilot reviews and requires `bot-review-complete`. Its name identifies the automatic review provider; the required status aggregates both bots.

The [resolve-pr-gate skill](https://github.com/zyplux/zyp-skills/tree/main/skills/resolve-pr-gate) reads `ci` and `bot-review-complete`, reports unresolved findings from both bots, and refreshes the verdict after threads are resolved. Install it from `zyplux/zyp-skills` to automate the review loop.

Consuming repositories need at least one of Copilot or Codex Code Review enabled and must use the [caller workflow](../../.github/workflows/org_gate.yml). Install the [GitHub App](../review-events/README.md#github-app-setup) for automatic dispatch.
