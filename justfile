set shell := ["bash", "-euo", "pipefail", "-c"]

alias i := install
alias k := knip
alias tc := typecheck
alias l := lint
alias t := test
alias c := check
alias u := upgrade
alias ui := upgrade-interactive

# List available recipes.
default:
    @just --list

# Install both workspaces: bun + uv.
install:
    bun install
    uv sync --all-packages --all-groups

# Report unused files, deps, and exports: knip (JS) + vulture (Python).
knip:
    bun run knip
    uv run vulture

# Type-check both workspaces: tsc/bun for .ts, pyrefly for .py.
typecheck:
    bun run typecheck
    uv run pyrefly check

# Lint and format both workspaces with autofix, then verify org invariants with cerberus.
lint:
    bun run lint:fix
    bun run format
    uv run rumdl check --fix
    uv run rumdl fmt
    uv run ruff check --fix
    uv run ruff format
    uv run cerberus --fix

# Run tests for both workspaces. Optional arg filters by test name; never fails when nothing matches.
test name='':
    bun run test {{ if name == '' { '' } else { '-t "' + name + '"' } }}
    uv run pytest {{ if name == '' { '' } else { '-k "' + name + '"' } }} || [ "$?" -eq 5 ]

# Full gate across both workspaces: install, knip, typecheck, lint, test — autofix throughout.
check: install knip typecheck lint test

# Upgrade JS dependencies via ncu. Forwards extra args (e.g. `just u -i`).
upgrade *args='':
    bun run upgrade -- {{ args }}

# Interactively select and apply upgrades, then reinstall.
upgrade-interactive:
    bun run upgrade -- -i
    bun install

# Remove dependencies and caches from both workspaces.
clean:
    rm -rf node_modules
    rm -rf .venv .pytest_cache .ruff_cache .rumdl_cache
    find . -type d -name __pycache__ -prune -exec rm -rf {} +

# Upsert every org ruleset in rulesets/ to GitHub (source of truth). Needs gh authenticated with org-admin scope.
apply-org-ruleset:
    bun apps/apply-org-rulesets/src/index.ts
