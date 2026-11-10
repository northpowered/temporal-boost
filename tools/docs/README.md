# Documentation portal

The documentation project uses Python 3.13.9 and its own lockfile. Keep its
dependencies separate from the package's Python 3.10 environment.

## Build and test

```bash
uv sync --project tools/docs --locked
uv run --project tools/docs --locked python scripts/docs/build_portal.py --all --strict
uv run --project tools/docs --locked python scripts/docs/check_portal.py --site site
uv run --project tools/docs --locked playwright install chromium
uv run --project tools/docs --locked pytest -c tools/docs/pyproject.toml tools/docs/tests/
```

Build before running tests: artifact, browser, and rollback checks use the generated
`site/` directory. CI runs these steps in that order on Ubuntu 24.04. Built sites,
screenshots, and archives belong in ignored output directories or Actions artifacts.
Keep only source files and compatibility metadata in Git.

To preview under the GitHub Pages project path:

```bash
uv run --project tools/docs --locked python scripts/docs/build_portal.py --serve --all --mount /temporal-boost/
```

## Authoring

English and Russian content lives in `docs/en/` and `docs/ru/`. After an English
change, review the Russian translation and update its `source_sha256` in
`portal.toml`. Code fences must match between languages. Locale routes, navigation,
and page metadata are configured in `portal.toml`; shared theme settings are in
`../../zensical.toml` and templates in `overrides/`.

Shared assets live in `docs/_shared/`. `assets.json` records the provenance,
licenses, and checksums of vendored brand and font files. `baseline/routes.json`
records legacy URLs and anchors checked against each new build.

## Deployment and rollback

The documentation workflow builds and tests both locales before saving
`docs-portal-verified`. The same verified site is uploaded for Pages on `main`.
Successful builds retain this artifact for 30 days.

To roll back, run **Documentation portal** manually on `main` and set
`restore_run_id` to a successful main documentation run whose
`docs-portal-verified` artifact is still available. The workflow verifies the
source run, downloads and checks the artifact, and publishes it without rebuilding.
The rollback checker uses only the Python standard library.

Leave `restore_run_id` empty to build current sources. If an older artifact has
expired, revert the relevant documentation sources and run the normal build.
