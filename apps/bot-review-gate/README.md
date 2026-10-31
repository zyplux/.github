# Bot review gate

The reusable [org gate](../../.github/workflows/org_gate_base.yml) publishes the required `bot-review-complete` commit status for Copilot and Codex Code Review.

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

At least one bot must complete a clean review of the current PR head. Only bots that have started reviewing that commit participate; queued requests alone do not block. Copilot must have a successful check-run and a submitted review; Codex must have a completed `code_review` entry in its bot-authored `codex-review-state:v1` summary. Live GitHub review threads determine whether findings remain unresolved; summary resolution flags can be stale. Security Review alone does not satisfy Code Review. The gate also checks unresolved threads from both bots, including threads on earlier commits.

Only explicit quota-denial responses from the known bot accounts count as unavailable. API errors, failed checks, cancellations, and timeouts block the gate. Copilot's quota review must cover the current head; a newer check-run invalidates an earlier quota denial. Codex's quota response must have current-head context in its Code Review summary or submitted review. A newer review request or review activity supersedes the response.

## Running the gate

[bot_review_complete.py](src/bot_review_gate/bot_review_complete.py) reads `REPO`, `PR`, `GH_TOKEN`, and optional `SHA`. The workflow token needs `checks: read`, `pull-requests: read`, and `statuses: write`. When `SHA` is omitted, a manual refresh evaluates the live head. A watcher stops when the PR becomes draft or its head changes.

The gate waits up to 200 seconds for the PR to leave draft, then polls review state every 15 seconds for up to 30 minutes. It publishes verdict changes while waiting, so resolving findings can clear a failing status during that window. Reviews, issue comments, check-runs, and review threads are paginated.

The caller workflow refreshes the gate on PR and issue-comment activity. Polling reads reviews without triggering approval-gated workflow runs from Copilot review events. GitHub Actions has no thread-resolution trigger; resolve threads during an active watch or dispatch `org_gate` with the PR number to refresh it. Exit code zero means the watcher finished; the commit status carries the merge verdict. A pending status remains blocking after the watch window expires. API failures publish `error` and exit with code one.

## Rollout

Merge the shared workflow and script before applying the version-controlled org rulesets with `just apply-org-ruleset`. The `copilot-review` ruleset requests automatic Copilot reviews and requires `bot-review-complete`. Its name identifies the automatic review provider; the required status aggregates both bots.

The [resolve-pr-gate skill](https://github.com/zyplux/zyp-skills/tree/main/skills/resolve-pr-gate) reads `ci` and `bot-review-complete`, reports unresolved findings from both bots, and refreshes the verdict after threads are resolved. Install it from `zyplux/zyp-skills` to automate the review loop.

Consuming repositories need at least one of Copilot or Codex Code Review enabled and must call the shared workflow. Use the caller in the [root README](../../README.md) to enable PR/issue-comment refreshes and manual dispatch. Existing PR-only callers still start the watcher on pushes and ready transitions.
