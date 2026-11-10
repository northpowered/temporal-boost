"""Validate the final artifact, including legacy anchors, locale links, assets and SEO."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET  # noqa: S405 - parses locally generated sitemaps
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from build_portal import ROOT, load_manifest, validate_sources


MIN_SEARCH_INDEX_BYTES = 100


class Document(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.alternates: list[tuple[str, str]] = []
        self.switches: list[tuple[str, str]] = []
        self.canonicals: list[str] = []
        self.lang = ""
        self.description = ""
        self.title = ""
        self.in_title = False
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "html":
            self.lang = values.get("lang", "")
        if tag == "title":
            self.in_title = True
        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content", "")
        for attribute in ("href", "src", "action"):
            if values.get(attribute):
                self.links.append(values[attribute])
        if tag == "link" and values.get("rel") == "alternate" and values.get("hreflang"):
            self.alternates.append((values["hreflang"], values["href"]))
        if tag == "link" and values.get("rel") == "canonical":
            self.canonicals.append(values["href"])
        if tag == "a" and "data-portal-language" in values:
            self.switches.append((values["hreflang"], values["href"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data


class _PortalChecker:
    def __init__(self, site: Path, data: dict) -> None:
        self.site = site.resolve()
        self.data = data
        self.base = urlsplit(data["site_url"])
        self.errors: list[str] = []
        self.documents = {
            path.relative_to(self.site).as_posix(): Document(path.read_text()) for path in self.site.rglob("*.html")
        }
        self.baseline = json.loads((ROOT / "tools/docs/baseline/routes.json").read_text())

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def check_link(self, source: str, href: str) -> None:
        parsed = urlsplit(urljoin(self.data["site_url"] + source, href))
        if parsed.scheme not in {"http", "https"} or parsed.netloc != self.base.netloc:
            return
        if not parsed.path.startswith(self.base.path):
            self.errors.append(f"{source}: link escapes project prefix: {href}")
            return
        path = unquote(parsed.path[len(self.base.path) :])
        if not path or path.endswith("/"):
            path += "index.html"
        target = (self.site / path).resolve()
        if not target.is_relative_to(self.site) or not target.is_file():
            self.errors.append(f"{source}: missing target: {href}")
        elif parsed.fragment and path in self.documents:
            self.require(unquote(parsed.fragment) in self.documents[path].ids, f"{source}: missing anchor: {href}")

    def check_resources(self) -> None:
        for source, document in self.documents.items():
            # Directory URLs resolve relative links against the directory, not /index.html.
            url = (
                source.removesuffix("index.html")
                if source.endswith("/index.html") or source == "index.html"
                else source
            )
            for link in document.links:
                self.check_link(url, link)
            text = (self.site / source).read_text()
            self.require(str(ROOT) not in text and ".cache/docs-portal" not in text, f"{source}: staging path leak")
            self.require(
                "fonts.googleapis.com" not in text and "raw.githubusercontent.com" not in text,
                f"{source}: externally loaded font or brand asset",
            )
        for path in self.site.rglob("*.css"):
            for link in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", path.read_text()):
                if not link.startswith("data:"):
                    self.check_link(path.relative_to(self.site).as_posix(), link)

    def check_pages(self) -> None:
        for page in self.data["pages"]:
            expected = {
                locale["code"]: self.data["site_url"] + locale["url_prefix"] + page["route"]
                for locale in self.data["locales"]
            }
            expected["x-default"] = expected[self.data["default_language"]]
            for locale in self.data["locales"]:
                self._check_page(page, locale, expected)

    def _check_page(self, page: dict, locale: dict, expected: dict[str, str]) -> None:
        code = locale["code"]
        path = locale["url_prefix"] + page["route"] + "index.html"
        self.require(path in self.documents, f"Missing page: {path}")
        if path not in self.documents:
            return
        doc = self.documents[path]
        self.require(set(page["anchors"]) <= doc.ids, f"{path}: fragment switch map includes nonexistent anchors")
        self.require(doc.lang == code, f"{path}: html lang {doc.lang!r}, expected {code}")
        self.require(doc.canonicals == [expected[code]], f"{path}: wrong canonical: {doc.canonicals}")
        self.require(
            len(doc.alternates) == len(expected) and dict(doc.alternates) == expected,
            f"{path}: wrong reciprocal hreflang: {doc.alternates}",
        )
        switches = {lang: urlsplit(url).path for lang, url in expected.items() if lang != "x-default"}
        self.require(dict(doc.switches) == switches, f"{path}: language selector does not preserve page")
        self.require(
            doc.description == page["descriptions"][code] and bool(doc.title), f"{path}: missing localized metadata"
        )
        edit = f"https://github.com/northpowered/temporal-boost/edit/main/docs/{locale['source']}/{page['source']}"
        self.require(edit in doc.links, f"{path}: edit link does not target the locale source")
        if code == self.data["default_language"] and page["source"] in self.baseline["pages"]:
            anchors = set(self.baseline["pages"][page["source"]]["anchors"])
            self.require(anchors <= doc.ids, f"{path}: lost legacy anchors: {sorted(anchors - doc.ids)}")

    def check_legacy_assets(self) -> None:
        for asset, checksum in self.baseline["assets"].items():
            path = self.site / asset
            self.require(
                path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == checksum,
                f"Legacy asset missing or changed: {asset}",
            )

    def check_sitemaps(self) -> None:
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = set()
        try:
            index = ET.parse(self.site / "sitemap.xml")  # noqa: S314 - generated by the local portal build
            for element in index.findall("s:sitemap/s:loc", ns):
                self.check_link("", element.text)
                local = element.text.removeprefix(self.data["site_url"])
                sitemap = ET.parse(self.site / local)  # noqa: S314 - generated by the local portal build
                sitemap_urls.update(el.text for el in sitemap.findall("s:url/s:loc", ns))
            expected_urls = {
                self.data["site_url"] + loc["url_prefix"] + page["route"]
                for loc in self.data["locales"]
                for page in self.data["pages"]
            }
            self.require(sitemap_urls == expected_urls, "Sitemaps do not cover exactly all locale pages")
        except (OSError, ET.ParseError) as error:
            self.errors.append(f"Invalid sitemap: {error}")

    def check_search(self) -> None:
        for locale in self.data["locales"]:
            search = self.site / locale["url_prefix"] / "search.json"
            self.require(
                search.is_file() and search.stat().st_size > MIN_SEARCH_INDEX_BYTES,
                f"Missing search index for {locale['code']}",
            )
            if search.is_file():
                try:
                    index = json.loads(search.read_text())
                    self.require(
                        index["config"]["lang"] == [locale["code"]], f"Wrong search language: {locale['code']}"
                    )
                    for item in index["items"]:
                        location = item["location"]
                        self.require(
                            not location.startswith(("/", "http:", "https:")), f"Non-local search result: {location}"
                        )
                        self.check_link(locale["url_prefix"], location)
                except (ValueError, KeyError, TypeError) as error:
                    self.errors.append(f"Invalid search index for {locale['code']}: {error}")


def check_portal(site: Path, data: dict | None = None) -> None:
    data = data or load_manifest()
    validate_sources(data)
    checker = _PortalChecker(site, data)
    checker.check_resources()
    checker.check_pages()
    checker.check_legacy_assets()
    checker.check_sitemaps()
    checker.check_search()
    checker.require((checker.site / ".nojekyll").is_file(), "Missing .nojekyll")
    checker.require(not (checker.site / "CNAME").exists(), "Project site must not carry a CNAME")
    checker.require(
        "Страница не найдена" in (checker.site / "404.html").read_text(), "Root 404 must offer EN/RU navigation"
    )
    if checker.errors:
        raise ValueError("Portal validation failed:\n" + "\n".join(checker.errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    check_portal(parser.parse_args().site)
