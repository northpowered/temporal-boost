from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup
from build_portal import ROOT, load_manifest, stage_locale
from fontTools.ttLib import TTFont
from restore_portal import check_restored_site, restore_baseline


def test_extensions_and_native_tags_are_rendered(tmp_path: Path) -> None:
    data = copy.deepcopy(load_manifest())
    config = stage_locale(data, data["locales"][0], tmp_path)
    docs = config.parent / "docs"
    (docs / "fragment.txt").write_text("SNIPPET_CAPABILITY_VERIFIED\n")
    (docs / "index.md").write_text("""---
tags:
  - capability
---
# Capability probe

## Stable heading {#stable-heading}

| Column | Value |
| --- | --- |
| table | rendered |

<div class="probe" markdown>
**HTML Markdown**
</div>

!!! note "Admonition"
    Admonition content

??? note "Details"
    Collapsible content

- [x] Task checkbox

`#!python print("inline")`

```python
print("fenced")
```

--8<-- "fragment.txt"

=== "Python"
    Tab content
""")
    subprocess.run(
        [str(Path(sys.executable).with_name("zensical")), "build", "-f", str(config), "--clean", "--strict"],
        check=True,
        cwd=ROOT,
    )
    soup = BeautifulSoup((config.parent / "output/index.html").read_text(), "html.parser")
    assert soup.select_one("#stable-heading")
    assert soup.select_one("table tbody td").text == "table"
    assert soup.select_one(".probe strong").text == "HTML Markdown"
    assert soup.select_one(".admonition.note")
    assert soup.select_one("details summary")
    assert soup.select_one('input[type="checkbox"][checked]')
    assert soup.select_one("code.highlight")
    assert soup.select_one(".highlight pre code .nb")
    assert "SNIPPET_CAPABILITY_VERIFIED" in soup.get_text()
    assert soup.select_one(".tabbed-set")
    assert any("capability" in tag.get_text() for tag in soup.select(".md-tag"))


def test_asset_provenance_checksums() -> None:
    for asset in json.loads((ROOT / "tools/docs/assets.json").read_text()):
        path = ROOT / "docs/_shared" / asset["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]


def test_local_font_contains_latin_and_cyrillic_glyphs() -> None:
    with TTFont(ROOT / "docs/_shared/assets/fonts/InterVariable.woff2") as font:
        characters = font.getBestCmap()
        assert all(ord(character) in characters for character in "TemporalКонфигурацияЁёЙй")


def test_core_dependencies_remain_isolated() -> None:
    root = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert root["project"]["requires-python"] == ">=3.10.0,<4.0.0"
    assert "docs" not in root["tool"]["uv"]["default-groups"]
    assert all("zensical" not in dep and "playwright" not in dep for dep in root["project"]["dependencies"])
    assert root["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_old_site_can_be_restored(tmp_path: Path) -> None:
    baseline = ROOT / "tools/docs/baseline"
    data = json.loads((baseline / "routes.json").read_text())
    with zipfile.ZipFile(baseline / "site.zip") as archive:
        assert archive.testzip() is None
        archive.extractall(tmp_path)
    for page in data["pages"].values():
        soup = BeautifulSoup((tmp_path / page["route"] / "index.html").read_text(), "html.parser")
        assert set(page["anchors"]) <= {tag["id"] for tag in soup.select("[id]")}


def test_baseline_restores_through_the_active_deployment_input(tmp_path: Path) -> None:
    destination = tmp_path / "site"
    restore_baseline(destination)
    check_restored_site(destination)
