from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from build_portal import ROOT
from restore_portal import check_restored_site, verify_run


def test_fresh_build_can_be_validated_for_rollback_without_docs_dependencies(tmp_path: Path) -> None:
    # CI builds site/ before running tests. Use that same artifact as a download.
    destination = tmp_path / "site"
    shutil.copytree(ROOT / "site", destination)
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(ROOT / "scripts/docs/restore_portal.py"), "--site", str(destination)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("index.html", "complete site"),
        ("404.html", "complete site"),
        (".nojekyll", "missing .nojekyll"),
        ("CNAME", "no CNAME"),
    ],
)
def test_invalid_downloaded_artifact_is_rejected(tmp_path: Path, mutation: str, message: str) -> None:
    destination = tmp_path / "site"
    shutil.copytree(ROOT / "site", destination)
    if mutation == "CNAME":
        (destination / mutation).write_text("example.com\n")
    else:
        (destination / mutation).unlink()
    with pytest.raises(ValueError, match=message):
        check_restored_site(destination)


def test_retired_baseline_input_is_rejected_before_downloading(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESTORE_RUN_ID", "baseline")
    with pytest.raises(ValueError, match="positive workflow run ID"):
        verify_run()
