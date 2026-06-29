# Org workflow distribution

Status: planned — distribution is not yet automated.

## Mechanism

`zyplux/.github` is the source of truth for org-wide workflows and rulesets:

```text
workflows/ci.yml
workflows/copilot-review-gate.yml
rulesets/default-branch-baseline.json
```

Distribute by **scripted sync**, not GitHub's native `workflow-templates/` feature.

Why not `workflow-templates/`: that feature only offers starter workflows in the
"New workflow" UI. A developer opts in per repo, the file is copied once, and the
copies drift. It never guarantees a workflow is present or identical across repos —
but the `copilot-review` required check needs the gate present on `main` in every
covered repo, or pull requests there block forever on an unreported check.

`workflows/` lives at the repo root on purpose: GitHub only executes
`.github/workflows/`, so these canonical copies never run inside `.github` itself
(which is excluded from the ruleset anyway).

## justfile responsibilities

1. Apply the ruleset — `PUT orgs/zyplux/rulesets/{id}` from `rulesets/`, the same
   upsert `czyp apply-org-rulesets` already performs.
2. Sync the workflows — copy `workflows/*` into each covered repo's
   `.github/workflows/` and commit.

## Covered repos

`zyp-cerberus`, `zyp-vps`, `totchef`, `zyplux-ai`, `zyp`, `zyp-skills`, `zyp-ocr`
(`~ALL` except `.github` and `zyplux-ai-pages`).

## Constraints

- Sync the workflows to all covered repos **before** applying the ruleset. An
  unreported required `copilot-review` check blocks every pull request in any repo
  that lacks the gate.
- `copilot-review-gate.yml` triggers on `workflow_run` and `pull_request_review`,
  which always run the **default-branch** version of the workflow. The gate only
  takes effect once it is on each repo's `main` — it cannot be exercised from a
  feature-branch pull request.
