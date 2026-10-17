"""Open the built catalogue in a browser and check that its pages work.

The docs build proves that the pages compile and link; this proves that their scripts run: the
charts draw, the region filter filters, a click highlights a region, and the comparison table
switches. Run it against `npm run preview` (``make ui-smoke`` starts that for you)::

    uv run --with playwright python scripts/ui_smoke.py http://localhost:4321/scope-profiler-catalog

``playwright install chromium`` installs the browser it uses; set ``BROWSER`` to the path of
another Chrome or Chromium to use that instead.
"""

from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = (
    sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4321/scope-profiler-catalog"
).rstrip("/")
failures: list[str] = []


def check(name: str, ok: bool, detail="") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("BROWSER") or None
    )
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    # The console says "404" without saying which file, so note the failed requests instead.
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )

    # The catalogue index is the front page.
    page.goto(f"{BASE}/", wait_until="networkidle")
    check(
        "the front page is the catalogue table",
        page.locator("table tbody tr").count() >= 1,
    )

    # A run page of several ranks.
    page.goto(f"{BASE}/catalogue/solvers/poisson-strong/np4/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    regions = page.locator("table.region-stats > tbody[data-region]")
    check("the region table lists the regions", regions.count() >= 3, regions.count())
    open_charts = page.locator(".chart.js-plotly-plot").count()
    check("the open charts draw", open_charts >= 1, open_charts)
    page.fill("#region-filter", "solve")
    page.wait_for_timeout(400)
    check(
        "the filter narrows the table",
        page.locator("table.region-stats > tbody[data-region]:not([hidden])").count()
        == 1,
    )
    page.fill("#region-filter", "")
    page.locator(".hotspot").first.click()
    page.wait_for_timeout(600)
    check(
        "a hotspot click highlights its row",
        page.locator(".region-row.region-selected").count() >= 1,
    )
    page.click("[data-chart-action=expand]")
    page.wait_for_timeout(2500)
    total = page.locator(".chart").count()
    check(
        "every chart draws once expanded",
        page.locator(".chart.js-plotly-plot").count() == total,
        total,
    )
    page.evaluate("document.documentElement.dataset.theme = 'light'")
    page.wait_for_timeout(1200)
    check(
        "the charts redraw on a theme switch",
        page.locator(".chart.js-plotly-plot").count() == total,
    )
    check("no script errors on a run page", not errors, errors[:3])

    # The showcase run: detail rows, line profile, hardware counters.
    errors.clear()
    page.goto(f"{BASE}/catalogue/fields/turbulence/baseline/", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.locator("table.region-stats tr.region-row", has_text="solve").first.click()
    page.wait_for_timeout(300)
    check(
        "a row opens its line profile",
        page.locator("tr.region-detail:not([hidden]) table.lp-table").count() == 1,
    )
    check(
        "hardware counters are listed",
        page.locator("details.counter-panel").count() >= 1,
    )
    check("no script errors on the showcase page", not errors, errors[:3])

    # A case page: the comparison.
    errors.clear()
    page.goto(f"{BASE}/catalogue/solvers/poisson-strong/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    check(
        "what changed lists the candidates",
        page.locator(".compare-candidate").count() >= 1,
    )
    table = "table.compare-table"
    page.click("[data-compare-metric=own]")
    check(
        "the comparison table switches metric",
        "metric-own" in (page.get_attribute(table, "class") or ""),
    )
    page.click("[data-compare-sort=change]")
    check(
        "the comparison table orders by change",
        "flat" in (page.get_attribute(table, "class") or ""),
    )
    check(
        "the comparison charts draw", page.locator(".chart.js-plotly-plot").count() >= 1
    )
    check("no script errors on a case page", not errors, errors[:3])
    browser.close()

print(f"\n{len(failures)} failure(s)" if failures else "\nall checks passed")
sys.exit(1 if failures else 0)
