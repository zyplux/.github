default:
    @just --list

# apply auto-fixes and verify: install, lint + format, tests
c:
    uv sync --locked
    uv run ruff check --fix
    uv run ruff format
    uv run pytest
