# zyplux/.github

This is the special `.github` repository for the **zyplux** organization.

It powers the public organization profile content shown at:
<https://github.com/zyplux>

Profile source file:

- `profile/README.md`

## Reusable CI

### org_gate_base

Watches the GitHub Copilot pull-request review and records it on a requireable
`copilot-review-complete` commit status (see [docs](docs/copilot-review-gate.md)).
Every org repo that the `default-branch-baseline` ruleset covers must call it, or
its PRs block forever on the missing status.

Copilot's review is re-triggered only by a flip → push → flip cycle (the push must
land _between_ the draft and ready flips); a manual draft↔ready flip, or a push
that lands after (or before for non-first) the ready flip, requests no review. Drive pushes with
`just pr` / `cz push-branch --ready`, never flip the PR by hand — see
[the draft-event race](docs/copilot-review-gate.md#the-draft-event-race).

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
