"""Validate the source run and downloaded artifact for a Pages rollback."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path


def verify_run() -> None:
    """Only accept successful production runs of this repository's docs workflow.

    Raises:
        ValueError: The run ID is invalid or the run is not a successful main documentation deployment.
    """
    run_id = os.environ["RESTORE_RUN_ID"]
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("RESTORE_RUN_ID must be a positive workflow run ID")
    repository = os.environ["GITHUB_REPOSITORY"]
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/runs/{run_id}",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS GitHub API origin
        run = json.load(response)
    if (
        run["conclusion"] != "success"
        or run["head_branch"] != "main"
        or run["event"] == "pull_request"
        or run["path"] != ".github/workflows/documentation.yml"
    ):
        raise ValueError("Restore source must be a successful main documentation deployment run")


def check_restored_site(site: Path) -> None:
    if not (site / "index.html").is_file() or not (site / "404.html").is_file():
        raise ValueError("Restore must contain a complete site with a root 404")
    if (site / "CNAME").exists() or any(path.is_symlink() for path in site.rglob("*")):
        raise ValueError("Restore must contain no CNAME or symlinks")
    if not (site / ".nojekyll").is_file():
        raise ValueError("Restore is missing .nojekyll")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-run", action="store_true")
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[2] / "site")
    args = parser.parse_args()
    if args.verify_run:
        verify_run()
    else:
        check_restored_site(args.site)
