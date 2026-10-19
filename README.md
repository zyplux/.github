# <img src="docs/assets/logo.svg" alt="" width="24"> zyplux/.github

<div align="center">

<img src="docs/assets/og.png" alt="Zyplux — Neural Intelligence Systems" width="640">

**The [Zyplux](https://zyplux.ai) org-wide `.github` repo** — the public organization profile, the reusable bot review gate, and the org rulesets as code.

</div>

## What's inside

| Piece                                                 | What it is                                                                    |
| ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| [profile/README.md](profile/README.md)                | Public org profile rendered at [github.com/zyplux](https://github.com/zyplux) |
| [org_gate_base](.github/workflows/org_gate_base.yml)  | Reusable workflow gating merges on clean reviews from available bots                  |
| [bot-review-gate](apps/bot-review-gate)       | The app behind org_gate_base — records the review verdict as a commit status   |
| [apply-org-rulesets](apps/apply-org-rulesets)         | Applies the org rulesets across every repo                                    |
| [rulesets](rulesets)                                  | Organization-wide branch protections and bot review requirements            |

## Reusable CI: org_gate_base

The shared [bot review gate](apps/bot-review-gate/README.md) requires clean Copilot and Codex Code Reviews for the current PR head. An explicit quota denial from one bot is accepted when the other completes a clean review. Unresolved findings from either bot always block merging. Missing, pending, stale, or unreadable review evidence keeps the gate blocking.

Every repository covered by the `copilot-review` ruleset must call the workflow and enable both reviewers. The ruleset requests Copilot automatically; configure Codex automatic reviews in its GitHub integration.

Add `.github/workflows/org_gate.yml` to the consuming repo:

```yaml
name: org_gate

on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  pull_request_review:
    types: [submitted, edited, dismissed]
  pull_request_review_comment:
    types: [created, edited, deleted]
  issue_comment:
    types: [created, edited, deleted]
  workflow_dispatch:
    inputs:
      pr:
        description: Pull request number to refresh
        required: true
        type: string

permissions:
  statuses: write
  checks: read
  pull-requests: read

jobs:
  org_gate_base:
    if: github.event_name != 'issue_comment' || github.event.issue.pull_request != null
    uses: zyplux/.github/.github/workflows/org_gate_base.yml@main
    with:
      pr: ${{ inputs.pr || '' }}
```

## Organization rulesets

`default-branch-baseline` requires CI, one approving review, code-owner review, resolved review threads, and squash merges for every repository. It also protects the default branch from deletion and force pushes.

`copilot-review` adds automatic Copilot reviews and the required `bot-review-complete` status for every repository in the organization.

Merge the shared gate and workflow caller updates before applying the version-controlled rules with `just apply-org-ruleset`. Every repository must publish the required `bot-review-complete` status to satisfy the org ruleset.
