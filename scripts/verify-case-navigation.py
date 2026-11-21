"""Exercise live case navigation in Chromium; SITE_URL points at a running site."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("SITE_URL", "http://localhost:4391").rstrip("/")
OUT = Path(os.environ.get("CASE_NAV_EVIDENCE", ROOT / ".cache/case-navigation-browser"))
OUT.mkdir(parents=True, exist_ok=True)
ROUTES = json.loads((ROOT / "project/doc-routes.json").read_text())
ARCHIVE_LANDING = re.compile(r"^archive/(?:[^/]+/)?index\.mdx$")
checks: list[str] = []
errors: list[str] = []


def check(name, passed):
    if not passed:
        raise AssertionError(name)
    checks.append(name)


def route_for(file):
    slug = file.removesuffix(".mdx").removesuffix("/index")
    return f"/docs/{slug}/"


def doc_link(scope, slug):
    return scope.locator(f'a[href="/docs/{slug}"], a[href="/docs/{slug}/"]')


def sidebar(page, width):
    if width < 1024:
        toggle = page.get_by_role("button", name="Open sidebar", exact=True)
        if toggle.count():
            toggle.click()
        scope = page.locator("aside[data-zd-mobile-sidebar] nav[data-sidebar-context]")
    else:
        scope = page.locator("nav[data-sidebar-context]:visible")
    expect(scope).to_have_count(1)
    expect(scope).to_be_visible()
    return scope


def nav_hrefs(scope):
    return scope.locator("[data-sidebar-tree-root] a[href]").evaluate_all(
        "links => links.map(a => new URL(a.href).pathname.replace(/\\/$/, ''))"
    )


def visit(page, route):
    response = page.goto(BASE + route, wait_until="networkidle")
    check(route + " HTTP 200", response is not None and response.status == 200)
    check(route + " no horizontal page overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"))


def branch_row(scope, slug):
    return doc_link(scope, slug).locator("xpath=ancestor::*[@data-sidebar-row][1]")


def exercise_printed(page, width):
    # Printed shows only the current P5 tree; P4/P3 live under the top-level Archive.
    visit(page, "/docs/printed-5mm/")
    nav = sidebar(page, width)
    expected_top = ["printed-5mm/p5-design"]
    for slug in expected_top:
        expect(doc_link(nav, slug)).to_have_count(1)
    check(f"{width} printed linked root", doc_link(nav, "printed-5mm").count() == 1)
    check(f"{width} initial Broaden absent at section ceiling", nav.locator("[data-sidebar-broaden]").count() == 0)
    for old in ["printed-5mm/p4-design", "printed-5mm/design", "printed-5mm/history"]:
        check(f"{width} printed sidebar omits superseded {old}", doc_link(nav, old).count() == 0)
    actual = nav_hrefs(nav)
    expected = [route_for(row["canonical"]).rstrip("/") for row in ROUTES["entries"] if row["owner"] == "printed-5mm"]
    check(f"{width} every current printed canonical link once", sorted(actual) == sorted(expected) and len(actual) == len(set(actual)))
    check(f"{width} printed sidebar has no archive link", not any(href.startswith("/docs/archive") for href in actual))
    page.screenshot(path=str(OUT / f"printed-current-{width}.png"), full_page=True)

    focus = branch_row(nav, "printed-5mm/p5-design").locator("[data-sidebar-focus]")
    focus.focus()
    page.keyboard.press("Enter")
    expect(nav.locator("[data-sidebar-broaden]")).to_be_visible()
    checks.append(f"{width} keyboard focus narrows to P5")
    nav.locator("[data-sidebar-broaden]").click()
    expect(nav.locator("[data-sidebar-broaden]")).to_have_count(0)
    check(f"{width} Broaden returns to printed root and stops", doc_link(nav, "printed-5mm").count() == 1)

    if width < 1024:
        nav.locator(":scope > button").click()
        menu = page.locator("aside[data-zd-mobile-sidebar]")
        case_toggle = menu.get_by_role("button", name="Expand ケース", exact=True)
        case_toggle.focus()
        page.keyboard.press("Enter")
        expect(menu.get_by_role("button", name="Collapse ケース", exact=True)).to_have_attribute("aria-expanded", "true")
        for slug in ["metal-case", "printed-5mm", "tenbox-v2", "two-way"]:
            expect(doc_link(menu, slug)).to_have_count(1)
            expect(doc_link(menu, slug)).to_be_visible()
        checks.append("390 mobile keyboard menu exposes all four independent case families")
        page.screenshot(path=str(OUT / "mobile-case-menu-390.png"), full_page=True)
        doc_link(menu, "tenbox-v2").click()
        page.wait_for_url("**/docs/tenbox-v2*")
        check("390 mobile family navigation reaches tenbox-v2", urlparse(page.url).path.rstrip("/") == "/docs/tenbox-v2")
    else:
        case = page.locator('header a[data-nav-category="overview"][aria-haspopup="true"]')
        case.focus()
        expect(case).to_have_attribute("aria-expanded", "true")
        for section in ["metal-case", "printed-5mm", "tenbox-v2", "two-way"]:
            expect(page.locator(f'header [data-nav-item-dropdown] a[data-nav-category="{section}"]')).to_be_visible()
        checks.append("1440 keyboard focus opens case dropdown with four children")
        page.keyboard.press("Escape")
        expect(case).to_have_attribute("aria-expanded", "false")
        checks.append("1440 Escape closes keyboard dropdown")


def exercise_sections(page, width):
    representatives = {
        "overview": "overview/start", "metal-case": "metal-case/status",
        "tenbox-v2": "tenbox-v2/printing", "two-way": "two-way",
        "shared": "shared", "development": "development/maintenance",
        "archive": "archive/metal-case",
    }
    for section, slug in representatives.items():
        visit(page, f"/docs/{slug}/")
        nav = sidebar(page, width)
        check(f"{width} {section} linked native root", doc_link(nav, section).count() == 1)
        check(f"{width} {section} current page owner", doc_link(nav, slug).get_attribute("aria-current") == "page")
        check(f"{width} {section} cannot broaden out of section", nav.locator("[data-sidebar-broaden]").count() == 0)
        check(f"{width} {section} only its own links", all(href == "/docs/" + section or href.startswith("/docs/" + section + "/") for href in nav_hrefs(nav)))
        if section in ["tenbox-v2", "development", "archive"]:
            page.screenshot(path=str(OUT / f"{section}-{width}.png"), full_page=True)
        if width >= 1024:
            owner = page.locator(f'header a[data-nav-category="{section}"]')
            check(f"{width} {section} header active owner", any(owner.nth(i).get_attribute("aria-current") == "page" or owner.nth(i).get_attribute("data-active") is not None for i in range(owner.count())))



def exercise_origin(page, width):
    visit(page, "/docs/tenbox-v2/preview/")
    iframe = page.locator('iframe[src*="tenbox-v2-r5.html"]')
    expect(iframe).to_have_count(1)
    src = urljoin(BASE + "/", iframe.get_attribute("src"))
    expected = os.environ.get("EXPECTED_PREVIEW_ORIGIN", BASE).rstrip("/")
    check(f"{width} integrated 10BOX iframe expected preview origin", src.split("/previews/")[0] == expected)
    response = page.request.get(src)
    check(f"{width} integrated iframe HTTP GET", response.status == 200 and "10BOX" in response.text())
    page.screenshot(path=str(OUT / f"tenbox-iframe-{width}.png"), full_page=True)


def exercise_archive(page, width):
    visit(page, "/docs/archive/")
    for project in ["metal-case", "printed-5mm"]:
        expect(page.locator(f'main a[href^="/docs/archive/{project}"]').first).to_be_visible()
    checks.append(f"{width} archive landing links project archives")
    visit(page, "/docs/archive/metal-case/design/r10-fullset-01/")
    check(f"{width} archived R10 page shows the archive banner", page.locator("text=アーカイブ（履歴）").count() > 0)
    check(f"{width} archived R10 page points to current R11", page.locator('main a[href*="/docs/metal-case/design/r11-build-feedback-04"]').count() > 0)
    for current in ["/docs/metal-case/design/r11-build-feedback-04/", "/docs/printed-5mm/ventilation/"]:
        visit(page, current)
        pager = page.locator("[data-doc-pager] a[href]").evaluate_all("links => links.map(a => new URL(a.href).pathname)")
        check(f"{width} {current} prev/next stays out of the archive", not any(href.startswith("/docs/archive") for href in pager))
    page.screenshot(path=str(OUT / f"current-r11-{width}.png"), full_page=True)


def exercise_search(page):
    response = page.request.get(BASE + "/search-index.json")
    check("search index GET HTTP 200", response.status == 200)
    index = response.json()
    searched = {item["url"].rstrip("/") for item in index if not str(item.get("id", "")).startswith("asset:")}
    for row in ROUTES["entries"]:
        canonical = route_for(row["canonical"]).rstrip("/")
        if row["canonical"].startswith("archive/") and not ARCHIVE_LANDING.match(row["canonical"]):
            check("search excludes archive detail " + row["canonical"], canonical not in searched)
        else:
            check("search canonical " + row["canonical"], canonical in searched)
        old = ([row["source"]] if row.get("source") and row["source"] != row["canonical"] else []) + [a["path"] for a in row.get("aliases", [])]
        for source in old:
            check("search excludes compatibility " + source, route_for(source).rstrip("/") not in searched)
    page.keyboard.press("Control+k")
    input_box = page.locator("[data-search-input]")
    expect(input_box).to_be_visible()
    input_box.fill("10BOX")
    result = page.locator('[data-search-results] a[href^="/docs/tenbox-v2"]')
    expect(result.first).to_be_visible()
    checks.append("live search returns canonical 10BOX-v2 pages")
    page.screenshot(path=str(OUT / "search-10box.png"), full_page=True)
    page.keyboard.press("Escape")
    expect(input_box).not_to_be_visible()
    checks.append("search Escape closes dialog")


def main():
    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--no-sandbox", "--enable-unsafe-swiftshader"]}
        executable = os.environ.get("CHROMIUM_EXECUTABLE")
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        report = {"base": BASE, "browser": browser.version, "checks": checks, "errors": errors, "passed": False}
        page = None
        try:
            for width in [1440, 390]:
                context = browser.new_context(viewport={"width": width, "height": 1000})
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                exercise_printed(page, width)
                exercise_sections(page, width)
                exercise_origin(page, width)
                exercise_archive(page, width)
                if width == 1440:
                    exercise_search(page)
                context.close()
            check("no browser JavaScript errors", not errors)
            report["passed"] = True
        except Exception as error:
            report["failure"] = str(error)
            if page and not page.is_closed():
                page.screenshot(path=str(OUT / "failure.png"), full_page=True)
            raise
        finally:
            (OUT / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            browser.close()
        print(f"Case navigation: {len(checks)} checks passed; evidence {OUT}")


if __name__ == "__main__":
    main()
