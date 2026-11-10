"""Build isolated locale sites, validate them, and atomically replace the Pages artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import http.server
import json
import re
import shutil
import subprocess  # noqa: S404 - runs the installed Zensical executable without a shell
import sys
import tempfile
import xml.etree.ElementTree as ET  # noqa: S405 - only serializes generated sitemap elements
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit

import tomli_w
import tomllib
import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools/docs/portal.toml"
CACHE = ROOT / ".cache/docs-portal"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(value: str, *, directory: bool = False) -> str:
    """Reject traversal, ambiguous URLs, and unsafe artifact paths.

    Raises:
        ValueError: The path is unsafe or does not match the required format.
    """
    path = Path(value)
    if "\\" in value or "?" in value or "#" in value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe relative path: {value!r}")
    if value and ("//" in value or value.startswith(".") or (directory and not value.endswith("/"))):
        raise ValueError(f"Invalid relative path: {value!r}")
    return value


def _validate_locales(data: dict) -> None:
    locales = data["locales"]
    codes = [locale["code"] for locale in locales]
    prefixes = [relative_path(locale["url_prefix"], directory=True) for locale in locales]
    if len(set(codes)) != len(codes) or len(set(prefixes)) != len(prefixes):
        raise ValueError("Locale codes and URL prefixes must be unique")
    if data["default_language"] not in codes or prefixes[codes.index(data["default_language"])]:
        raise ValueError("The default locale must own the project root")
    for locale in locales:
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]+)*", locale["code"]):
            raise ValueError("Invalid locale code")
        relative_path(locale["source"])
    for prefix in prefixes:
        if any(other and prefix.startswith(other) and prefix != other for other in prefixes):
            raise ValueError("Nested locale prefixes are not supported")


def _validate_pages(data: dict, groups: list[str]) -> None:
    ids, sources, outputs = set(), set(), set()
    reserved = {"assets", "img", "search", "404.html", "sitemap.xml", "portal-routes.json"}
    for page in data["pages"]:
        source = relative_path(page["source"])
        route = relative_path(page["route"], directory=True)
        if not source.endswith(".md") or source in sources or page["page_id"] in ids:
            raise ValueError("Page IDs and Markdown source paths must be unique")
        if page["group"] not in groups:
            raise ValueError(f"Unknown navigation group: {page['group']}")
        if route.split("/")[0] in reserved:
            raise ValueError(f"Reserved output route: {route}")
        # Source filenames intentionally define the same routes in every locale.
        expected = "" if source == "index.md" else source.removesuffix(".md") + "/"
        if route != expected:
            raise ValueError(f"Route {route!r} does not match source {source!r}")
        ids.add(page["page_id"])
        sources.add(source)
        for locale in data["locales"]:
            code = locale["code"]
            if code not in page["titles"] or code not in page["descriptions"]:
                raise ValueError(f"Missing localized metadata for {page['page_id']}/{code}")
            output = locale["url_prefix"] + route + "index.html"
            if output in outputs:
                raise ValueError(f"Output collision: {output}")
            outputs.add(output)


def load_manifest(path: Path = MANIFEST) -> dict:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    _validate_locales(data)
    groups = [group["id"] for group in data["groups"]]
    if len(groups) != len(set(groups)):
        raise ValueError("Navigation groups must be unique")
    if any(locale["code"] not in group["labels"] for group in data["groups"] for locale in data["locales"]):
        raise ValueError("Every navigation group must have a label in each locale")
    _validate_pages(data, groups)
    site = urlsplit(data["site_url"])
    if site.scheme != "https" or not site.netloc or not site.path.endswith("/"):
        raise ValueError("site_url must be an absolute HTTPS URL ending in /")
    return data


def validate_sources(data: dict, root: Path = ROOT) -> None:
    """Translations require a reviewed hash, full page coverage, and unchanged code.

    Raises:
        ValueError: Page coverage, translation review, or code fences fail validation.
    """
    source_locale = next(loc for loc in data["locales"] if loc["code"] == data["default_language"])
    expected = {page["source"] for page in data["pages"]}
    for locale in data["locales"]:
        directory = root / "docs" / locale["source"]
        found = {p.relative_to(directory).as_posix() for p in directory.rglob("*.md")}
        if found != expected:
            raise ValueError(
                f"Source coverage for {locale['code']}: missing {expected - found}, extra {found - expected}"
            )
        for page in data["pages"]:
            if locale == source_locale:
                continue
            original = root / "docs" / source_locale["source"] / page["source"]
            translated = directory / page["source"]
            review = page.get("translations", {}).get(locale["code"], {})
            if review.get("status") != "reviewed" or review.get("source_sha256") != source_hash(original):
                raise ValueError(f"Unreviewed or stale translation: {locale['code']}/{page['source']}")
            # Keep signatures, payload keys, commands, and examples byte-for-byte identical.
            fences = r"(?ms)^[ \t]*```[^\n]*\n.*?^[ \t]*```[^\n]*"
            if re.findall(fences, original.read_text()) != re.findall(fences, translated.read_text()):
                raise ValueError(f"Code fences differ in {locale['code']}/{page['source']}")


def page_links(data: dict, page: dict) -> list[dict]:
    return [
        {
            "lang": locale["code"],
            "name": locale["label"],
            "link": urlsplit(data["site_url"]).path + locale["url_prefix"] + page["route"],
            "anchors": page.get("anchors", []),
        }
        for locale in data["locales"]
    ]


def stage_locale(data: dict, locale: dict, workspace: Path) -> Path:
    folder = workspace / locale["code"]
    folder.mkdir()
    docs = folder / "docs"
    shutil.copytree(ROOT / "docs" / locale["source"], docs)
    shutil.copytree(ROOT / "docs/_shared", docs, dirs_exist_ok=True)
    shutil.copytree(ROOT / "tools/docs/overrides", folder / "overrides")
    config = copy.deepcopy(tomllib.loads((ROOT / "zensical.toml").read_text()))
    project = config["project"]
    project["markdown_extensions"]["pymdownx.snippets"]["base_path"] = str(docs)
    project.update(docs_dir="docs", site_dir="output", site_url=data["site_url"] + locale["url_prefix"])
    project["site_description"] = locale["description"]
    project["theme"].update(language=locale["code"], custom_dir="overrides")
    project["theme"]["palette"][0]["toggle"]["name"] = locale["light_toggle"]
    project["theme"]["palette"][1]["toggle"]["name"] = locale["dark_toggle"]
    project["edit_uri"] = f"edit/main/docs/{locale['source']}/"
    project["copyright"] = locale["copyright"]
    extra = project.setdefault("extra", {})
    extra["scope"] = urlsplit(data["site_url"]).path
    extra["search_strings"] = locale["search_strings"]
    extra["search_result_count"] = locale["search_result_count"]
    extra["origin"] = data["site_url"].removesuffix(urlsplit(data["site_url"]).path)
    extra["alternate"] = [
        {"lang": loc["code"], "name": loc["label"], "link": urlsplit(data["site_url"]).path + loc["url_prefix"]}
        for loc in data["locales"]
    ]
    extra["routes"] = {page["route"]: page_links(data, page) for page in data["pages"]}
    extra["defaults"] = {page["route"]: urlsplit(data["site_url"]).path + page["route"] for page in data["pages"]}
    nav = []
    for group in data["groups"]:
        entries = [
            {page["titles"][locale["code"]]: page["source"]} for page in data["pages"] if page["group"] == group["id"]
        ]
        if entries:
            nav.append({group["labels"][locale["code"]]: entries})
    project["nav"] = nav
    for page in data["pages"]:
        path = docs / page["source"]
        content = path.read_text()
        metadata = {}
        if content.startswith("---\n"):
            frontmatter, content = content[4:].split("\n---\n", 1)
            metadata = yaml.safe_load(frontmatter) or {}
        metadata.update(title=page["titles"][locale["code"]], description=page["descriptions"][locale["code"]])
        path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + content)
    config_path = folder / "zensical.toml"
    config_path.write_text(tomli_w.dumps(config))
    return config_path


def write_metadata(data: dict, destination: Path, locales: list[dict]) -> None:
    routes = {page["page_id"]: page_links(data, page) for page in data["pages"]}
    (destination / "portal-routes.json").write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n")
    (destination / ".nojekyll").touch()
    ET.register_namespace("", SITEMAP_NS)
    index = ET.Element(f"{{{SITEMAP_NS}}}sitemapindex")
    for locale in locales:
        sitemap = ET.Element(f"{{{SITEMAP_NS}}}urlset")
        for page in data["pages"]:
            url = ET.SubElement(sitemap, f"{{{SITEMAP_NS}}}url")
            ET.SubElement(url, f"{{{SITEMAP_NS}}}loc").text = data["site_url"] + locale["url_prefix"] + page["route"]
        name = f"sitemap-{locale['code']}.xml"
        ET.ElementTree(sitemap).write(destination / name, encoding="utf-8", xml_declaration=True)
        entry = ET.SubElement(index, f"{{{SITEMAP_NS}}}sitemap")
        ET.SubElement(entry, f"{{{SITEMAP_NS}}}loc").text = data["site_url"] + name
    ET.ElementTree(index).write(destination / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    # Absolute project-prefixed links work even when Pages serves this at a missing nested URL.
    links = " · ".join(
        f'<a href="{urlsplit(data["site_url"]).path}{loc["url_prefix"]}" lang="{loc["code"]}">{loc["label"]}</a>'
        for loc in data["locales"]
    )
    (destination / "404.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<meta name="robots" content="noindex"><title>404 · Temporal-boost</title>'
        "<style>body{font:1.2rem system-ui;background:#141414;color:#f8fafc;"
        "max-width:45rem;margin:10vh auto;padding:2rem}"
        "a{color:#c7d2fe}a:focus-visible{outline:3px solid #c7d2fe}</style>"
        '<h1>404 · Page not found</h1><p lang="ru">Страница не найдена.</p>'
        "<p>Choose documentation / Выберите документацию:</p>" + links + "</html>"
    )


def assemble(data: dict, locales: list[dict], workspace: Path, destination: Path) -> None:
    """Copy only verified builds; never let a locale's --clean remove its neighbor.

    Raises:
        ValueError: Two locale builds claim the same artifact path.
    """
    destination.mkdir()
    claimed = set()
    for locale in locales:
        output = workspace / locale["code"] / "output"
        for source in output.rglob("*"):
            if not source.is_file():
                continue
            relative = Path(locale["url_prefix"]) / source.relative_to(output)
            if relative in claimed:
                raise ValueError(f"Artifact path collision: {relative}")
            claimed.add(relative)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    write_metadata(data, destination, locales)


def build(data: dict, locale_code: str | None = None, *, strict: bool = True) -> Path:
    validate_sources(data)
    selected = [loc for loc in data["locales"] if locale_code is None or loc["code"] == locale_code]
    if not selected:
        raise ValueError(f"Unknown locale: {locale_code}")
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=CACHE) as temporary:
        workspace = Path(temporary)
        for locale in selected:
            config = stage_locale(data, locale, workspace)
            command = [
                str(Path(sys.executable).with_name("zensical")),
                "build",
                "--config-file",
                str(config),
                "--clean",
            ]
            if strict:
                command.append("--strict")
            subprocess.run(command, check=True, cwd=ROOT)  # noqa: S603 - local executable and generated config, no shell
        pending = workspace / "artifact"
        assemble(data, selected, workspace, pending)
        if locale_code is None:
            from check_portal import check_portal  # noqa: PLC0415 - checker imports shared build helpers

            check_portal(pending, data)
        destination = ROOT / "site" if locale_code is None else CACHE / f"preview-{locale_code}"
        # Preserve the previous valid artifact through failures and restore it if replacement fails.
        previous = workspace / "previous"
        if destination.exists():
            destination.rename(previous)
        try:
            pending.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
        return destination


def serve(site: Path, mount: str, port: int) -> None:
    relative_path(mount.lstrip("/"), directory=True)
    with tempfile.TemporaryDirectory(prefix="preview-", dir=CACHE) as directory:
        mounted = Path(directory) / mount.strip("/")
        mounted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(site, mounted, dirs_exist_ok=True)
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=directory)
        with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
            server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="Build all manifest locales (default)")
    selection.add_argument("--locale", help="Build one locale for authoring")
    parser.add_argument("--strict", action="store_true", help="Explicit strict mode (always enabled)")
    parser.add_argument("--serve", action="store_true", help="Serve the build over HTTP; rerun after edits")
    parser.add_argument("--mount", default="/temporal-boost/")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    data = load_manifest()
    destination = build(data, args.locale)
    if args.serve:
        serve(destination, args.mount, args.port)


if __name__ == "__main__":
    main()
