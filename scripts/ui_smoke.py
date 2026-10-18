"""Open the built catalogue in a browser and check that its pages work.

The docs build proves that the pages compile and link; this proves that their scripts run: the
charts draw, the region filter filters, a click highlights a region, and the comparison table
switches. Run it against `npm run preview` (``make ui-smoke`` starts that for you)::

    uv run --with playwright python scripts/ui_smoke.py http://localhost:4321/scope-profiler-catalog [docs]

``docs`` is the Astro project (default ``docs``), where the generated page data is read from.

``playwright install chromium`` installs the browser it uses; set ``BROWSER`` to the path of
another Chrome or Chromium to use that instead.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (
    sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4321/scope-profiler-catalog"
).rstrip("/")
DOCS = Path(sys.argv[2] if len(sys.argv) > 2 else "docs")
failures: list[str] = []


def same(left, right, tolerance=1e-9) -> bool:
    """Equal, numbers to a relative tolerance (JavaScript and Python print floats differently)."""
    if (
        isinstance(left, bool)
        or isinstance(right, bool)
        or left is None
        or right is None
    ):
        return left is right or left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=tolerance, abs_tol=1e-15)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            same(left[k], right[k]) for k in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            same(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


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

    # The sidebar lists a case once, not each of its runs.
    sidebar = page.locator(".sidebar-content a").all_inner_texts()
    check(
        "the sidebar lists the case",
        "Poisson solver, strong scaling" in sidebar,
        sidebar[:12],
    )
    check(
        "the sidebar does not list the runs",
        not {"np1", "np2", "np4", "np8"} & set(sidebar),
        sidebar[:12],
    )
    check(
        "a run page links its neighbours",
        page.locator("a[href$='/np2/']").count() >= 1,
    )

    # Picking the two runs to compare.
    page.locator("#sp-compare-all").uncheck()
    page.wait_for_timeout(300)
    check(
        "a pair shows one comparison", page.locator(".compare-candidate").count() == 1
    )
    page.select_option("#sp-compare-base", label="np2")
    page.select_option("#sp-compare-cand", label="np8")
    page.wait_for_timeout(300)
    check(
        "the pair is the one picked",
        page.locator(".compare-candidate h3").inner_text() == "np8 vs np2",
        page.locator(".compare-candidate h3").inner_text(),
    )
    check(
        "the table shows the pair",
        page.locator(".compare-table thead th").all_inner_texts()[:3]
        == ["region", "np2", "np8"],
        page.locator(".compare-table thead th").all_inner_texts(),
    )
    durations_id = (
        page.locator(
            ".chart-panel", has=page.locator("summary", has_text="Region durations")
        )
        .locator(".chart")
        .first.get_attribute("id")
    )
    page.wait_for_timeout(1200)
    drawn_runs = page.evaluate(
        f"[...new Set(document.getElementById('{durations_id}').data.map((t) => t.name))]"
    )
    check(
        "the durations chart follows the compared runs",
        sorted(drawn_runs) == ["np2", "np8"],
        drawn_runs,
    )
    cells = page.locator(".compare-table tbody tr").first.locator("td").count()
    check("every row has a cell for each run and its change", cells == 1 + 1 + 2, cells)
    check(
        "the choice is in the URL",
        "base=np2" in page.url and "cand=np8" in page.url,
        page.url,
    )
    page.click("#sp-compare-swap")
    page.wait_for_timeout(300)
    check(
        "swap exchanges them",
        page.locator(".compare-candidate h3").inner_text() == "np2 vs np8",
    )
    page.select_option(
        "#sp-compare-base", label="np8"
    )  # the candidate is np8 too: it moves aside
    page.wait_for_timeout(300)
    check(
        "one run is never compared with itself",
        page.locator(".compare-candidate h3").inner_text().split(" vs ")[0]
        != page.locator(".compare-candidate h3").inner_text().split(" vs ")[1],
    )
    page.goto(
        f"{BASE}/catalogue/solvers/poisson-strong/?base=np4&cand=np8&runs=pair",
        wait_until="networkidle",
    )
    page.wait_for_timeout(1500)
    check(
        "a shared link opens that comparison",
        page.locator(".compare-candidate h3").inner_text() == "np8 vs np4",
    )

    # The page's comparison is computed in the browser; it must agree with the report's own.
    data = json.loads(
        (
            DOCS / "src/content/docs/catalogue/solvers/poisson-strong.data.json"
        ).read_text()
    )["report"]
    count = len(data["candidates"]) + 1
    in_page = page.evaluate(
        """(count) => { const c = window.scopeProfilerCompare; const runs = [...Array(count).keys()];
           return { candidates: c.candidateModels(c.dataset, runs), table: c.compareTableModel(c.dataset, runs) }; }""",
        count,
    )
    check(
        "the browser's what-changed matches the report's",
        same(in_page["candidates"], data["candidates"]),
    )
    check(
        "the browser's durations table matches the report's",
        same(in_page["table"], data["table"]),
    )

    # Axis scales: log2 and log10 on a numeric axis; none on a categorical one.
    page.goto(f"{BASE}/catalogue/solvers/poisson-strong/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    speedup = page.locator(
        ".chart-panel", has=page.locator("summary", has_text="Speedup")
    ).first
    chart_id = speedup.locator(".chart").get_attribute("id")

    def axis(name):
        return page.evaluate(
            f"document.getElementById('{chart_id}')._fullLayout.{name}axis.type"
        )

    check(
        "a numeric axis offers the scales",
        speedup.locator(".chart-scale[data-axis-name=y]").is_visible(),
    )
    speedup.locator("button[data-scale-axis=y][data-scale=log2]").click()
    page.wait_for_timeout(1500)
    ticks = page.evaluate(
        f"document.getElementById('{chart_id}')._fullLayout.yaxis.tickvals"
    )
    check(
        "log2 draws a log axis with ticks at powers of two",
        axis("y") == "log" and ticks and all(math.log2(t).is_integer() for t in ticks),
        (axis("y"), ticks),
    )
    speedup.locator("button[data-scale-axis=y][data-scale=log10]").click()
    page.wait_for_timeout(1500)
    check(
        "log10 draws a log axis",
        axis("y") == "log" and axis("x") == "linear",
        (axis("x"), axis("y")),
    )
    speedup.locator("button[data-scale-axis=x][data-scale=log2]").click()
    page.wait_for_timeout(1500)
    check(
        "the x axis scales on its own",
        axis("x") == "log" and axis("y") == "log",
        (axis("x"), axis("y")),
    )
    speedup.locator("button[data-scale-axis=x][data-scale=linear]").click()
    speedup.locator("button[data-scale-axis=y][data-scale=linear]").click()
    page.wait_for_timeout(1500)
    check(
        "linear restores the axes",
        axis("x") == "linear" and axis("y") == "linear",
        (axis("x"), axis("y")),
    )
    durations = page.locator(
        ".chart-panel", has=page.locator("summary", has_text="Region durations")
    ).first
    check(
        "a categorical axis has no scales",
        not durations.locator(".chart-scale[data-axis-name=x]").is_visible(),
    )
    check(
        "its numeric axis has",
        durations.locator(".chart-scale[data-axis-name=y]").is_visible(),
    )
    browser.close()

print(f"\n{len(failures)} failure(s)" if failures else "\nall checks passed")
sys.exit(1 if failures else 0)
