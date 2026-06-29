# copilot-review-gate

A reusable workflow that watches the GitHub Copilot pull-request review and
records its result on a `copilot-review-complete` commit status, so the org
ruleset can require Copilot review as a merge gate. A clean review records
`success`; unresolved Copilot comments record `failure` and flip the PR back to
draft.

## Why a watcher is needed

- The native `copilot-pull-request-reviewer` check-run shows up in the REST
  `commits/{sha}/check-runs` API but is excluded from the PR status rollup, so it
  can never satisfy a required status check — it would stay "Expected" forever.
- The Copilot check-run and review are created by the `github-actions` app using
  `GITHUB_TOKEN`, and GitHub never starts a workflow from a `GITHUB_TOKEN`
  -triggered event (recursion prevention). So a `check_run` or
  `pull_request_review` watcher would never fire — the gate must trigger on the
  human-initiated `pull_request` event and poll the check-runs API instead.

## How it works

The consuming repo's caller triggers on `pull_request`
(`opened`, `reopened`, `synchronize`, `ready_for_review`) and delegates to this
reusable workflow, which runs `scripts/copilot_review_gate.py`. The script:

1. Waits for the PR's ready flip by polling live draft state, then waits a short
   window for Copilot's check-run to appear. If it never appears (Copilot was not
   triggered — e.g. a flip-flip), it posts a blocking `failure` within minutes
   instead of hanging.
2. Once the check-run completes, it does **not** trust the conclusion alone (see
   [The completion race](#the-completion-race)). It waits for Copilot's review to
   be submitted on the head SHA, then counts unresolved review threads authored by
   Copilot:
   - zero → records `success`; the PR can auto-merge.
   - one or more → records `failure` and converts the PR back to draft, so its
     at-rest state honestly reads "your turn". Resolve the threads, then `just pr`.
3. Filters the check-runs poll with `check_name` + `per_page=100`; the unfiltered
   endpoint paginates at 30, so the Copilot run could fall off the first page.
4. Posts a definitive status and exits 0 for every verdict it can determine —
   success, or a blocking `failure`/`error`. It exits non-zero only when it
   genuinely cannot read state (draft state, check-runs, or review threads
   unreadable), so the job check goes red on a real machinery fault, never merely
   on a blocked PR.

## The completion race

Copilot marks its check-run `completed` with conclusion `success` **1–2 seconds
before** it submits the review and its comments — measured directly on real PRs —
and the conclusion is `success` even when the review leaves blocking comments. So
the check-run carries no "has comments" signal and turns green slightly too early.

Keying `copilot-review-complete` off the check-run alone is therefore unsafe: the
status could go green in the gap before any review thread exists. In that gap `ci`
and `copilot-review-complete` are both green and there are zero threads, so
`required_review_thread_resolution` has nothing to block on and auto-merge can
fire on a PR that is about to receive comments. The watcher closes the gap by
waiting for the review submission (atomic with its comments) and counting threads
before it records success — and `pull-requests: write` lets it flip the PR to
draft when those threads exist.

## The draft-event race

Copilot's auto-review fires on `ready_for_review` **only when a push landed
between the draft and ready flips** — flip → push → flip (`cz push-branch
--ready` does this and refuses when there is nothing to push). Flip → flip, or
flip → flip → push (the push arrives as a `synchronize` on an already-ready PR),
requests no review. Driving the flips by hand instead of through `just pr` is how
a PR ends up ready with no Copilot review on its head SHA.

That cycle fires `synchronize` (draft) then `ready_for_review` (ready) in quick
succession, and GitHub does not reliably spawn a workflow run for the
`ready_for_review` event when it lands within seconds of the push. So the gate
must not gate on the event-payload draft flag or skip the `synchronize` run —
every run polls the live draft state and records from whichever fires.

The concurrency group is keyed on `repository` + PR number + the event-payload
`draft` flag. Keying on the draft flag puts the `synchronize` (draft) run and the
`ready_for_review` (ready) run of one push in *separate* groups, so they do not
cancel each other — both complete and post a success status. Cancelling one (a
PR-number-only group) would leave a cancelled check-run on the head, which the PR
UI renders as a failing check even though the surviving run succeeded. The
redundant second run is cheap (the job is mostly idle polling). A genuinely newer
push still supersedes the prior run within the same draft phase, and the key
never collides across repos.
