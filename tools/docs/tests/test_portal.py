from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import build_portal
import pytest
import tomli_w
from build_portal import ROOT, load_manifest, stage_locale, validate_sources
from check_portal import check_portal


def test_final_artifact() -> None:
    check_portal(ROOT / "site")


@pytest.mark.parametrize("mutation", ["duplicate", "traversal", "collision", "missing_title"])
def test_manifest_rejects_invalid_routes(tmp_path: Path, mutation: str) -> None:
    data = copy.deepcopy(load_manifest())
    if mutation == "duplicate":
        data["locales"].append(data["locales"][0])
    elif mutation == "traversal":
        data["pages"][0]["source"] = "../secrets.md"
    elif mutation == "collision":
        data["pages"][0]["route"] = "assets/"
    else:
        del data["pages"][0]["titles"]["ru"]
    path = tmp_path / "portal.toml"
    path.write_text(tomli_w.dumps(data))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_source_changes_require_translation_review(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    path = tmp_path / "docs/en/configuration.md"
    path.write_text(path.read_text() + "\nA changed configuration contract.\n")
    with pytest.raises(ValueError, match="stale translation"):
        validate_sources(load_manifest(), root=tmp_path)


def test_translation_cannot_change_commands(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    path = tmp_path / "docs/ru/index.md"
    path.write_text(path.read_text().replace("pip install temporal-boost", "pip install other-package"))
    with pytest.raises(ValueError, match="Code fences differ"):
        validate_sources(load_manifest(), root=tmp_path)


def test_third_language_uses_the_same_staging_code(tmp_path: Path) -> None:
    data = copy.deepcopy(load_manifest())
    locale = {**data["locales"][1], "code": "de", "source": "en", "url_prefix": "de/", "label": "Deutsch"}
    data["locales"].append(locale)
    for page in data["pages"]:
        page["titles"]["de"] = page["titles"]["en"]
        page["descriptions"]["de"] = page["descriptions"]["en"]
    for group in data["groups"]:
        group["labels"]["de"] = group["labels"]["en"]
    config = stage_locale(data, locale, tmp_path)
    import tomllib

    project = tomllib.loads(config.read_text())["project"]
    assert project["site_url"].endswith("/temporal-boost/de/")
    assert project["theme"]["language"] == "de"
    assert project["extra"]["routes"]["configuration/"][2]["link"] == "/temporal-boost/de/configuration/"
    assert (config.parent / "docs/assets/fonts/InterVariable.woff2").is_file()


def test_second_locale_failure_preserves_previous_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for directory in ["docs", "tools/docs/overrides"]:
        shutil.copytree(ROOT / directory, tmp_path / directory)
    shutil.copy(ROOT / "zensical.toml", tmp_path / "zensical.toml")
    (tmp_path / "site").mkdir()
    (tmp_path / "site/previous.html").write_text("previous verified site")
    monkeypatch.setattr(build_portal, "ROOT", tmp_path)
    monkeypatch.setattr(build_portal, "CACHE", tmp_path / ".cache")
    calls = []

    def run(command: list[str], **kwargs: object) -> None:
        calls.append(command)
        if len(calls) == 2:
            raise subprocess.CalledProcessError(1, command)
        config = Path(command[command.index("--config-file") + 1])
        (config.parent / "output").mkdir()
        (config.parent / "output/index.html").write_text("partial EN output")

    monkeypatch.setattr(build_portal.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        build_portal.build(load_manifest())
    assert len(calls) == 2
    assert (tmp_path / "site/previous.html").read_text() == "previous verified site"
    assert not (tmp_path / "site/index.html").exists()


@pytest.mark.parametrize("mutation", ["asset", "anchor", "hreflang", "search"])
def test_checker_rejects_broken_artifacts(tmp_path: Path, mutation: str) -> None:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "site", site)
    if mutation == "asset":
        (site / "assets/fonts/InterVariable.woff2").unlink()
    elif mutation == "search":
        path = site / "ru/search.json"
        data = json.loads(path.read_text())
        data["config"]["lang"] = ["en"]
        path.write_text(json.dumps(data))
    else:
        path = site / "configuration/index.html"
        text = path.read_text()
        if mutation == "anchor":
            text = text.replace('id="configuration-priority"', 'id="lost-priority"')
        else:
            text = text.replace('hreflang="ru"', 'hreflang="de"')
        path.write_text(text)
    with pytest.raises(ValueError):
        check_portal(site)
