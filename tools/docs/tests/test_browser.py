from __future__ import annotations

import functools
import http.server
import re
import shutil
import threading

import pytest
from build_portal import ROOT
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser


def contrast(first: str, second: str) -> float:
    def luminance(color: str) -> float:
        channels = [float(channel) / 255 for channel in re.findall(r"[\d.]+", color)[:3]]
        channels = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict=True))

    low, high = sorted((luminance(first), luminance(second)))
    return (high + 0.05) / (low + 0.05)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def portal_url(tmp_path_factory: pytest.TempPathFactory):
    directory = tmp_path_factory.mktemp("portal-http")
    shutil.copytree(ROOT / "site", directory / "temporal-boost")
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/temporal-boost/"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.mark.parametrize("locale", ["", "ru/"])
@pytest.mark.parametrize("route", ["", "configuration/", "api_reference/"])
@pytest.mark.parametrize("width", [360, 768, 1440])
@pytest.mark.parametrize("scheme", ["slate", "default"])
def test_layout_assets_and_screenshots(browser, portal_url: str, locale: str, route: str, width: int, scheme: str):
    context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("response", lambda response: errors.append(response.url) if response.status >= 400 else None)
    page.goto(portal_url + locale + route)
    page.wait_for_load_state("networkidle")
    if scheme == "default":
        page.locator('label[for="__palette_1"]').click()
    expect(page.locator("body")).to_have_attribute("data-md-color-scheme", scheme)
    expect(page.locator("html")).to_have_attribute("lang", "ru" if locale else "en")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert page.evaluate('document.fonts.check("16px Inter", "Конфигурация воркера")')
    assert page.locator(".md-header__title").inner_text().strip().startswith("Temporal-boost")
    assert page.locator("main h1").is_visible()
    background = page.locator("body").evaluate("el => getComputedStyle(el).backgroundColor")
    for selector in ["main p", "main p a"]:
        text = page.locator(selector).first
        foreground = text.evaluate("el => getComputedStyle(el).color")
        assert contrast(foreground, background) >= 4.5, (selector, scheme, foreground, background)
    cards = page.locator(".grid.cards li")
    if cards.count():
        border = cards.first.evaluate("el => getComputedStyle(el).borderTopColor")
        assert contrast(border, background) >= 3
    screenshots = ROOT / ".cache/docs-portal/screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    name = f"{locale.strip('/') or 'en'}-{route.strip('/') or 'home'}-{width}-{scheme}.png"
    page.screenshot(path=str(screenshots / name))
    assert errors == []
    context.close()


def test_language_keyboard_anchor_and_theme_preference(browser, portal_url: str):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    page.goto(portal_url + "configuration/#configuration-priority")
    page.locator('label[for="__palette_1"]').click()
    button = page.locator('button[aria-label="Select language"]')
    button.focus()
    page.keyboard.press("Tab")
    expect(page.locator('[data-portal-language][hreflang="en"]')).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    page.wait_for_url("**/ru/configuration/#configuration-priority")
    expect(page.locator("html")).to_have_attribute("lang", "ru")
    expect(page.locator("body")).to_have_attribute("data-md-color-scheme", "default")
    page.reload()
    expect(page.locator("body")).to_have_attribute("data-md-color-scheme", "default")
    page.goto(portal_url + "ru/configuration/#no-such-anchor")
    page.locator('button[aria-label="Выберите язык"]').focus()
    page.locator('[data-portal-language][hreflang="en"]').click()
    page.wait_for_url("**/temporal-boost/configuration/")
    context.close()


@pytest.mark.parametrize(
    "locale,query",
    [("", "worker"), ("", "graceful shutdown"), ("ru/", "конфигурация"), ("ru/", "завершение"), ("ru/", "воркер")],
)
def test_native_search_uses_current_locale(browser, portal_url: str, locale: str, query: str):
    context = browser.new_context()
    page = context.new_page()
    page.goto(portal_url + locale + "configuration/")
    page.locator(".md-search__button").click()
    field = page.get_by_role("combobox")
    if locale:
        expect(field).to_have_attribute("aria-label", "Поиск")
    field.fill(query)
    results = page.get_by_role("option")
    expect(results.first).to_be_visible(timeout=15000)
    for link in results.all():
        href = link.get_attribute("href")
        assert href.startswith(portal_url + locale)
        if not locale:
            assert not href.startswith(portal_url + "ru/")
    results.first.click()
    page.wait_for_load_state()
    expect(page.locator("html")).to_have_attribute("lang", "ru" if locale else "en")
    context.close()


def test_copy_mobile_drawer_and_zoom(browser, portal_url: str):
    context = browser.new_context(
        viewport={"width": 360, "height": 900}, permissions=["clipboard-read", "clipboard-write"]
    )
    page = context.new_page()
    page.goto(portal_url + "ru/")
    copy = page.locator('[data-md-type="copy"]').first
    copy.click()
    assert "pip install temporal-boost" in page.evaluate("navigator.clipboard.readText()")
    page.goto(portal_url + "ru/configuration/")
    page.locator('.md-header__button[for="__drawer"]').click()
    expect(page.locator("#__drawer")).to_be_checked()
    page.locator('.md-sidebar--primary a[href*="advanced_usage"]').click()
    page.wait_for_url("**/ru/advanced_usage/")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.evaluate('document.documentElement.style.zoom = "2"')
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    context.close()
