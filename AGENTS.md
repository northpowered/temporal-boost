# Repository Guidelines

## Project Structure & Module Organization

- `temporal_boost/` contains the published package. Core application and shared logic live at the package root; Temporal clients, configuration, runtime, and workers are organized in `temporal_boost/temporal/` and `temporal_boost/workers/`.
- `tests/` contains the pytest suite, with files named `test_<area>.py`.
- `examples/` contains runnable integration and usage examples; `docs/en/` and `docs/ru/` contain portal Markdown, and `docs/_shared/` contains local assets.
- `tools/docs/` is an isolated Python 3.13 documentation project. `zensical.toml` and `tools/docs/portal.toml` own shared settings and localized routes; `scripts/docs/` stages, builds, and checks the portal.
- `tools/docs/overrides/` contains shared theme templates; `tools/docs/baseline/routes.json` preserves legacy routes for compatibility checks. CI builds the site before testing and stores verified builds as Actions artifacts.
- Packaging and tool configuration are in `pyproject.toml`; dependencies are locked in `uv.lock`.

## Build, Test, and Development Commands

Use uv to create the environment and run project tools:

```bash
uv sync --locked
uv run pytest tests/ --cov=temporal_boost --cov-report=term
uv run ruff check temporal_boost/ examples/
uv run ruff format --check temporal_boost/ examples/
uv run mypy temporal_boost/
uv sync --project tools/docs --locked
uv run --project tools/docs --locked python scripts/docs/build_portal.py --all --strict
uv run --project tools/docs --locked python scripts/docs/check_portal.py --site site
uv run --project tools/docs --locked python scripts/docs/build_portal.py --serve --all --mount /temporal-boost/
```

Run examples with `uv run python examples/<file>.py` when their external services are available. Install optional integrations with `uv sync --extra faststream --extra uvicorn`.

Documentation browser checks are separate from the package suite:

```bash
uv run --project tools/docs --locked playwright install chromium
uv run --project tools/docs --locked pytest -c tools/docs/pyproject.toml tools/docs/tests/
```

Keep Python 3.10 support and documentation dependencies separate. Review the Russian translation whenever English changes, then update its source hash in `portal.toml`; do not refresh hashes without reviewing content. See `tools/docs/README.md` for authoring, provenance, and rollback. Rollback downloads a verified artifact from a successful main documentation run; do not commit built sites or ZIP archives.

## Coding Style & Naming Conventions

Target Python 3.10+. Use four-space indentation, double-quoted strings, type annotations, and a maximum line length of 120 characters. Ruff is the formatter and linter; run it before committing. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and descriptive worker, workflow, and activity names.

## Testing Guidelines

Add or update pytest tests in `tests/` for behavior changes. Keep test files named `test_<area>.py` and test functions named `test_<behavior>`. Prefer focused unit tests and async tests compatible with `pytest-asyncio`. Run the full suite with coverage before submitting a change.

## Commit & Pull Request Guidelines

Recent commits use short Conventional Commit prefixes such as `feat:`, `fix:`, `refactor:`, and `chore:`; keep subjects imperative and focused. Pull requests should explain the change, mention relevant issues, describe validation commands, and include documentation or example updates when user-facing behavior changes. Ensure CI checks pass before requesting review.

## Configuration & Security

Do not commit credentials or environment-specific settings. Configure Temporal connections and worker tuning through environment variables (for example, `TEMPORAL_TARGET_HOST` and `TEMPORAL_NAMESPACE`).

## Using Context7 MCP
When you need to search docs, use Context7
