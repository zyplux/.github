---
name: resolve-pr-review-comments
description: >
  Loop through GitHub Copilot review comments on a pull request until the
  `bot-review-complete` gate reads clean: read each unresolved Copilot thread,
  decide whether it is right, fix the code where you agree and reply with reasoning
  where you don't, resolve every thread, run `just pr` to refresh the gate (it
  pushes fixes to re-trigger a fresh review, or refreshes in place when nothing
  changed), wait for its verdict, and repeat. Auto-merge is enabled by the push and
  held by the gate until a head is clean. Use when the user runs
  /resolve-pr-review-comments or asks to address Copilot review comments on a PR.
  Drives the GitHub API via `gh`.
metadata:
  kind: prompt
  version: "0.6.0"
  user-invocable: "true"
  argument-hint: "[<pr-number-or-url>]"
---

# resolve-pr-review-comments

Invoked as `/resolve-pr-review-comments [<pr-number-or-url>]`. With no argument it
targets the current branch's PR. Prompt-driven: drive `gh` directly and supply the
judgment yourself.

Scope: **GitHub Copilot inline review threads** (author login matches `copilot`
case-insensitively, `__typename` is `Bot`). The PR's top-level review *summary* is
not a resolvable thread — read it for context only.

## How merge is gated

The org gate publishes `bot-review-complete` for the current head. Both Copilot and Codex Code Review must finish cleanly, except that an explicit quota denial from one bot permits a clean review from the other. Unresolved findings from either bot block merging; pending, missing, and stale reviews remain blocking.

This skill addresses Copilot threads. A blocking Codex finding or missing Codex review must be addressed separately before the aggregate gate can pass. Refresh the gate after resolving threads with the `org_gate` workflow dispatch, or use `just pr` for its ready transition. Stop retrying a quota-exhausted bot.

## Step 1 — identify the PR

```bash
PR_ARG='__ARGUMENT_OR_EMPTY__'   # the slash-command argument, or empty
OWNER=$(gh repo view --json owner -q .owner.login)
REPO=$(gh repo view --json name -q .name)
NUMBER=$(gh pr view $PR_ARG --json number -q .number)
```

If `gh pr view` reports no PR for the current branch and no argument was given,
stop and ask the user for the PR number — do not guess.

## Step 2 — check the gate, then read the threads

Read `bot-review-complete` on the head; if it is already `success`, skip to
Step 5.

```bash
SHA=$(git rev-parse HEAD)
gh api "repos/$OWNER/$REPO/commits/$SHA/statuses" \
  --jq 'map(select(.context=="bot-review-complete"))[0].state // "none"'
```

Otherwise read the unresolved Copilot threads and the diff for the cited files, so
your decision is grounded in the real code:

```bash
gh api graphql -F owner="$OWNER" -F name="$REPO" -F number="$NUMBER" -f query='
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      reviewThreads(first:100){
        nodes{
          id isResolved isOutdated path line
          comments(first:50){ nodes{ databaseId body author{ login __typename } } }
        }
      }
    }
  }
}'
gh pr diff "$NUMBER"
```

Keep threads where `isResolved` is false and the first comment's author is Copilot;
record each thread's `id`, `path`, `line`, and comment `body`.

## Step 3 — decide, reply, fix, and resolve every thread

Judge each comment on its merits against the real code — neither reflexively agree
(Copilot is often right, not always) nor reflexively defend the code. Honor the
repo's `CLAUDE.md`: idiomatic solutions, self-documenting names, fix-don't-silence.
Act on real bugs, correctness or security risks, clearer idiomatic forms, and
genuine standards violations; disagree with false positives, style contrary to the
repo's conventions, or out-of-scope suggestions.

Reply on each thread (not a new top-level comment). Where you **agree**, edit the
code in the working tree (the better long-term design, not the smallest diff), then
reply that it's addressed (e.g. "Done — extracted the guard into `ensure_loaded`.").
Where you **disagree**, give the reason in a sentence or two, referencing the code.
One fix may settle several threads — note it on each. Then resolve every processed
thread.

```bash
gh api graphql -f threadId='<thread-node-id>' -f body='<reply>' -f query='
mutation($threadId:ID!,$body:String!){
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId,body:$body}){ comment{ url } }
}'
gh api graphql -f threadId='<thread-node-id>' -f query='
mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ isResolved } } }'
```

**Commit every code fix before leaving this step.** `just pr` (Step 4) only pushes
*committed* work — a fix left uncommitted in the working tree is silently skipped, so
the head doesn't change. The moment all threads resolve, the gate flips to `success`
and the already-armed auto-merge fires on that unchanged head, **merging the PR without
your fix** while the thread reply claims it landed. After running `just c` to verify,
`git add` the touched files and `git commit` them. Then confirm the tree is clean and
HEAD has moved before Step 4:

```bash
git status --porcelain   # must be empty
git log --oneline -1     # must show your fix commit, not the pre-existing head
```

## Step 4 — refresh the gate and wait for its verdict

Run `just pr`. It pushes the current head, flips back to ready, and enables
auto-merge (which the gate holds until the head is clean). **Precondition: your fixes
are committed (Step 3) — `just pr` pushes commits, never the working tree.** If `just pr`
reports `Everything up-to-date` when you expected to push a fix, stop: the fix is
uncommitted, the head hasn't moved, and the gate is about to merge the old code. Commit,
then re-run.

- **Changed code** (you fixed valid comments) → `just pr` flips the PR to draft, pushes
  the fixes, and flips back to ready; that ready transition re-triggers a fresh Copilot
  review of the new commits.
- **No code change** (every thread was a disagreement) → there's nothing to push, so
  `just pr` does its draft→ready flip to re-run the watcher and re-count the
  now-resolved threads. It permits this only because Copilot already reviewed HEAD; it
  still refuses if you pre-pushed unreviewed commits.

Then wait for `bot-review-complete` on the current head to settle:

```bash
SHA=$(git rev-parse HEAD)
for _ in $(seq 1 120); do
  STATE=$(gh api "repos/$OWNER/$REPO/commits/$SHA/statuses" \
    --jq 'map(select(.context=="bot-review-complete"))[0].state // "none"')
  case "$STATE" in success|failure|error) break;; esac
  sleep 10
done
```

- `success` → go to Step 5.
- `failure` → return to **Step 2** for the next round. After **5 rounds** with
  threads still remaining, stop, disable auto-merge (`gh pr merge "$NUMBER"
  --disable-auto`), and report what's left — this guards against endless Copilot
  ping-pong.
- `error` or timeout → stop and tell the user (Copilot may be unavailable or out of
  quota, or the gate hit a machinery fault); don't spin forever.

## Step 5 — confirm the merge and report

Reached when `bot-review-complete` is `success`. The aggregate review requirement is satisfied; confirm every other
required check, so ensure auto-merge is enabled and let it merge — a `just pr` from
Step 4 may have already enabled it (or the PR may have merged already), so this is
idempotent:

```bash
gh pr merge "$NUMBER" --squash --auto --delete-branch 2>/dev/null || true
```

Read the PR state to see whether it merged or is queued, and report. Summarize per
round: agreed-and-fixed (with file:line and what changed) vs. disagreed (with the
reason given), and the final outcome.

## Notes

- The reply, resolve, ready-flip, and merge calls need a token with write access
  (the user's normal `gh auth`). On a permissions error, surface it and stop — don't
  retry blindly.
- Past 100 threads or 50 comments in a thread, paginate with the GraphQL
  `pageInfo`/`endCursor` cursors rather than silently truncating.
- Each push is a fresh head with no `bot-review-complete` yet, so merge can only
  happen once the gate re-posts `success` on the latest head with all threads
  resolved — the loop relies on this, it doesn't race it.
