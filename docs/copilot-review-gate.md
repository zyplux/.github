# copilot-review-gate

A reusable workflow that mirrors the GitHub Copilot pull-request review onto a
`copilot-review-complete` commit status, so the org ruleset can require Copilot
review as a merge gate.

## Why a mirror is needed

- The native `copilot-pull-request-reviewer` check-run shows up in the REST
  `commits/{sha}/check-runs` API but is excluded from the PR status rollup, so it
  can never satisfy a required status check — it would stay "Expected" forever.
- The Copilot check-run and review are created by the `github-actions` app using
  `GITHUB_TOKEN`, and GitHub never starts a workflow from a `GITHUB_TOKEN`
  -triggered event (recursion prevention). So a `check_run` or
  `pull_request_review` mirror would never fire — the gate must trigger on the
  human-initiated `pull_request` event and poll the check-runs API instead.

## How it works

The consuming repo's caller triggers on `pull_request`
(`opened`, `reopened`, `synchronize`, `ready_for_review`) and delegates to this
reusable workflow, which runs `scripts/copilot_review_gate.py`. The script:

1. Waits for the PR's ready flip by polling the live draft state, then waits for
   Copilot and mirrors its conclusion onto the `copilot-review-complete` status.
2. Filters the check-runs poll with `check_name` + `per_page=100`; the unfiltered
   endpoint paginates at 30, so the Copilot run could fall off the first page.
3. Fails loudly (posts an `error` status, exits non-zero) if it can never read
   the draft state, rather than silently leaving the status missing.

## The draft-event race

Re-triggering Copilot on a new commit requires the push to land inside a
draft→ready cycle (`cz push-branch --ready` flips draft, pushes, flips ready).
That cycle fires `synchronize` (draft) then `ready_for_review` (ready) in quick
succession, and GitHub does not reliably spawn a workflow run for the
`ready_for_review` event when it lands within seconds of the push. So the gate
must not gate on the event-payload draft flag or skip the `synchronize` run —
every run polls the live draft state and mirrors from whichever fires.

The concurrency group is keyed on `repository` + PR number + the event-payload
`draft` flag. Keying on the draft flag puts the `synchronize` (draft) run and the
`ready_for_review` (ready) run of one push in *separate* groups, so they do not
cancel each other — both complete and post a success status. Cancelling one (a
PR-number-only group) would leave a cancelled check-run on the head, which the PR
UI renders as a failing check even though the surviving run succeeded. The
redundant second run is cheap (the job is mostly idle polling). A genuinely newer
push still supersedes the prior run within the same draft phase, and the key
never collides across repos.
