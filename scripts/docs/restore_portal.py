"""Restore the recorded MkDocs baseline or validate a previously verified Pages artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
import zipfile
from pathlib import Path

from build_portal import ROOT
from check_portal import Document


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


def restore_baseline(destination: Path) -> None:
    if destination.exists():
        raise ValueError("Restore destination must not already exist")
    with zipfile.ZipFile(ROOT / "tools/docs/baseline/site.zip") as archive:
        for name in archive.namelist():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe archived path: {name}")
        if archive.testzip() is not None:
            raise ValueError("Corrupt baseline archive")
        archive.extractall(destination)
    (destination / ".nojekyll").touch()
    baseline = json.loads((ROOT / "tools/docs/baseline/routes.json").read_text())
    for page in baseline["pages"].values():
        document = Document((destination / page["route"] / "index.html").read_text())
        if not set(page["anchors"]) <= document.ids:
            raise ValueError(f"Baseline lost anchors: {page['route']}")


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
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    if args.verify_run:
        verify_run()
    else:
        if args.baseline:
            restore_baseline(args.site)
        check_restored_site(args.site)
