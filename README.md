# <img src="docs/assets/logo.svg" alt="" width="24"> zyplux/.github

<div align="center">

<img src="docs/assets/og.png" alt="Zyplux — Neural Intelligence Systems" width="640">

**The [Zyplux](https://zyplux.ai) org-wide `.github` repo** — the public organization profile, the reusable CI gate every repo calls, and the org rulesets as code.

</div>

## What's inside

| Piece                                                 | What it is                                                                    |
| ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| [profile/README.md](profile/README.md)                | Public org profile rendered at [github.com/zyplux](https://github.com/zyplux) |
| [org_gate_base](.github/workflows/org_gate_base.yml)  | Reusable workflow gating merges on a completed Copilot review                  |
| [copilot-review-gate](apps/copilot-review-gate)       | The app behind org_gate_base — records the review verdict as a commit status   |
| [apply-org-rulesets](apps/apply-org-rulesets)         | Applies the org rulesets across every repo                                    |
| [rulesets](rulesets)                                  | Org branch-protection rulesets as code (`default-branch-baseline`)            |

## Reusable CI: org_gate_base

Watches the GitHub Copilot pull-request review and records it on a requireable `copilot-review-complete` commit status (see [docs](apps/copilot-review-gate/README.md)). A clean review records `success`; unresolved Copilot comments record `failure`, blocking the merge until they are resolved. Every org repo that the `default-branch-baseline` ruleset covers must call it, or its PRs block forever on the missing status.

Copilot's review is re-triggered only by a flip → push → flip cycle (the push must land _between_ the draft and ready flips); a manual draft↔ready flip, or a push that lands after (or before for non-first) the ready flip, requests no review. Drive pushes with `just pr` / `cz push-branch --ready`, never flip the PR by hand — see [the draft-event race](apps/copilot-review-gate/README.md#the-draft-event-race).

Add `.github/workflows/org_gate.yml` to the consuming repo:

```yaml
name: org_gate

on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]

permissions:
  statuses: write
  checks: read
  pull-requests: read

jobs:
  org_gate_base:
    uses: zyplux/.github/.github/workflows/org_gate_base.yml@main
```
