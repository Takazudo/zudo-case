"""Headless offline checks; this script is intended for the integration manager."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


PREVIEW = Path(__file__).resolve().parent
R9_ROOT = PREVIEW.parent
HTML = PREVIEW.parents[2] / "public" / "previews" / "r9-prototype-01.html"
SHOTS = PREVIEW / "shots"
REPORT = R9_ROOT / "out" / "preview" / "browser-check.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, default=HTML)
    parser.add_argument("--shots", type=Path, default=SHOTS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    report = {
        "revision": "R9-PROTOTYPE-01",
        "model": "7u40",
        "status": "failed",
        "checks": {},
        "consoleErrors": [],
        "pageErrors": [],
        "networkRequests": [],
        "screenshots": [],
    }
    if not args.html.is_file():
        report["checks"]["htmlExists"] = False
        report["error"] = f"preview HTML missing: {args.html}"
        _write_report(args.report, report)
        return 1
    report["checks"]["htmlExists"] = True

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        report["error"] = "Playwright is not installed; see preview/README.md."
        _write_report(args.report, report)
        return 2

    args.shots.mkdir(parents=True, exist_ok=True)
    request_urls: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.on("request", lambda request: request_urls.append(request.url)
                    if urlsplit(request.url).scheme in ("http", "https", "ws", "wss") else None)
            page.on("console", lambda message: console_errors.append(message.text)
                    if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route("http://**", lambda route: route.abort())
            page.route("https://**", lambda route: route.abort())
            page.goto(args.html.resolve().as_uri(), wait_until="domcontentloaded")
            page.wait_for_function("!!window.ZUDO_R9_PREVIEW", timeout=30000)
            page.wait_for_function("document.getElementById('loading').hidden", timeout=30000)
            report["checks"]["revision"] = page.evaluate("window.ZUDO_R9_PREVIEW.revision")

            page.locator('[data-state="daily"]').click()
            page.wait_for_function("document.getElementById('statusText').textContent.includes('日常')")
            daily_path = args.shots / "r9-prototype-01-daily.png"
            page.screenshot(path=str(daily_path), full_page=True)
            report["screenshots"].append(str(daily_path))
            report["checks"]["dailyState"] = True

            page.locator('[data-state="travel"]').click()
            page.wait_for_function("document.getElementById('statusText').textContent.includes('運搬')")
            travel_path = args.shots / "r9-prototype-01-travel.png"
            page.screenshot(path=str(travel_path), full_page=True)
            report["screenshots"].append(str(travel_path))
            report["checks"]["travelState"] = True

            page.locator('[data-state="open"]').click()
            page.wait_for_function("document.getElementById('statusText').textContent.includes('開放')")
            page.evaluate("window.ZUDO_R9_PREVIEW.setLift(150)")
            report["checks"]["liftRange"] = page.locator("#lift").get_attribute("min") == "0" and \
                page.locator("#lift").get_attribute("max") == "150" and \
                page.locator("#liftValue").inner_text() == "150 mm"
            page.locator("#lift").evaluate("element => { element.value = '110'; element.dispatchEvent(new Event('input', {bubbles:true})); }")

            page.locator("#showKnobs").check()
            report["checks"]["provisionalKnobEnvelope"] = page.evaluate(
                "window.ZUDO_R9_PREVIEW.visiblePartCount('7U40-R9-PREVIEW-KNOB-ENVELOPE') > 0"
            )
            page.locator("#showThinGuards").check()
            report["checks"]["thinGuardComparison"] = page.evaluate(
                "window.ZUDO_R9_PREVIEW.visiblePartCount('7U40-R9-PA12-GUARD-T1P0-TOP-A') > 0"
            )
            page.locator("#showKnobs").uncheck()
            page.locator("#showThinGuards").uncheck()

            page.locator("#partList").evaluate("element => { element.closest('details').open = true; }")
            first_part = page.locator("#partList button").first
            part_id = first_part.get_attribute("data-part-id")
            first_part.click()
            report["checks"]["partInfoClick"] = bool(part_id) and part_id in page.locator("#partInfo").inner_text()
            report["checks"]["partInfoHasDimensions"] = "mm" in page.locator("#partInfo").inner_text()

            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(250)
            report["checks"]["mobileViewport"] = page.evaluate("({width: window.innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth})")
            report["checks"]["mobileNoHorizontalScroll"] = all(
                value <= 390 for value in report["checks"]["mobileViewport"].values()
            )
            mobile_path = args.shots / "r9-prototype-01-open-mobile.png"
            page.screenshot(path=str(mobile_path), full_page=True)
            report["screenshots"].append(str(mobile_path))

            report["networkRequests"] = request_urls
            report["consoleErrors"] = console_errors
            report["pageErrors"] = page_errors
            report["checks"]["noNetworkRequests"] = len(request_urls) == 0
            report["checks"]["noConsoleErrors"] = len(console_errors) == 0 and len(page_errors) == 0
            browser.close()
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        report["networkRequests"] = request_urls
        report["consoleErrors"] = console_errors
        report["pageErrors"] = page_errors
        _write_report(args.report, report)
        return 1

    passed = all(value is True for key, value in report["checks"].items()
                 if key not in ("mobileViewport", "revision")) and \
        report["checks"].get("revision") == "R9-PROTOTYPE-01"
    report["status"] = "passed" if passed else "failed"
    _write_report(args.report, report)
    return 0 if passed else 1


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
