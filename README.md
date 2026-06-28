# zyplux/.github

This is the special `.github` repository for the **zyplux** organization.

It powers the public organization profile content shown at:
https://github.com/zyplux

Profile source file:
- `profile/README.md`

## Reusable CI

### copilot-review-gate

Mirrors the GitHub Copilot pull-request review onto a requireable
`copilot-review-complete` commit status (see [docs](docs/copilot-review-gate.md)).
Every org repo that the `default-branch-baseline` ruleset covers must call it, or
its PRs block forever on the missing status.

Add `.github/workflows/copilot-review-gate.yml` to the consuming repo:

```yaml
name: copilot-review-gate

on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]

permissions:
  statuses: write
  checks: read
  pull-requests: read

jobs:
  mirror:
    uses: zyplux/.github/.github/workflows/copilot-review-gate.yml@main
```
