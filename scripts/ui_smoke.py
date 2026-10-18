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

    # One run's durations are stacked by default; the checkbox groups them.
    page.goto(f"{BASE}/catalogue/solvers/poisson-strong/np4/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    box = page.locator(".chart-stack-box").first
    check("a run's durations are stacked by default", box.is_checked())
    panel_id = box.get_attribute("data-chart")
    box.uncheck()
    page.wait_for_timeout(1500)
    segments = page.evaluate(
        f"[...new Set(document.getElementById('{panel_id}').data.map((t) => t.name))]"
    )
    check("unticking draws the bars without segments", "self" not in segments, segments)

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

    # Rank charts and the durations chart's "stack children" over the compared runs.
    check(
        "the comparison starts on a pair",
        page.locator(".compare-candidate").count() == 1,
    )
    check(
        "'every run' is unticked by default",
        not page.locator("#sp-compare-all").is_checked(),
    )
    page.click("[data-chart-action=expand]")
    page.wait_for_timeout(3000)
    titles = page.locator(".chart-panel summary").all_inner_texts()
    check(
        "a comparison has the rank charts",
        "Rank imbalance" in titles and "Rank heatmap" in titles,
        titles,
    )
    check(
        "they all draw",
        page.locator(".chart.js-plotly-plot").count() == page.locator(".chart").count(),
    )
    durations = page.locator(
        ".chart-panel", has=page.locator("summary", has_text="Region durations")
    ).first
    durations_id = durations.locator(".chart").get_attribute("id")

    def names():
        return page.evaluate(
            f"[...new Set(document.getElementById('{durations_id}').data.map((t) => t.name))]"
        )

    check("runs are grouped by default", set(names()) == {"np1", "np8"}, names())
    # The browser's builder stacks one run's segments only, so the comparison has no checkbox.
    check(
        "a comparison has no 'stack children'",
        durations.locator(".chart-stack-box").count() == 0,
    )

    # What identifies each run can be written above its bars.
    durations.locator(".bar-labels summary").click()
    durations.locator(".bar-label-box[data-key=label]").check()
    durations.locator(".bar-label-box[data-key=ranks]").check()
    page.wait_for_timeout(1500)
    texts = page.evaluate(
        f"document.getElementById('{durations_id}').data.map((t) => t.text)"
    )
    check(
        "the bars say which run they are",
        texts
        and texts[0]
        and texts[0][0] == "np1 · 1 rank"
        and texts[1][0] == "np8 · 8 ranks",
        [t[:1] for t in texts],
    )
    durations.locator(".bar-label-box[data-key=value]").check()
    page.wait_for_timeout(1500)
    texts = page.evaluate(
        f"document.getElementById('{durations_id}').data.map((t) => t.text)"
    )
    check(
        "the bar's value can be added",
        all(" · " in t[0] and t[0].endswith(("ms", "s")) for t in texts),
        [t[:1] for t in texts],
    )
    for key in ("label", "ranks", "value"):
        durations.locator(f".bar-label-box[data-key={key}]").uncheck()
    page.wait_for_timeout(1200)
    cleared = page.evaluate(
        f"document.getElementById('{durations_id}').data.every((t) => !t.text)"
    )
    check("unticking removes the labels", cleared)

    # "Open in new tab" draws the chart in the site's own colours, in either theme.
    for theme in ("dark", "light"):
        page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
        page.wait_for_timeout(1200)
        site_background = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--sl-color-bg').trim()"
        )
        with page.context.expect_page() as popup_info:
            durations.locator(".chart-open").click()
        popup = popup_info.value
        popup.wait_for_load_state("load")
        popup.wait_for_timeout(2500)
        background = popup.evaluate("getComputedStyle(document.body).backgroundColor")
        paper = popup.evaluate(
            "document.getElementById('chart')._fullLayout.paper_bgcolor"
        )
        check(
            f"the new tab has the {theme} theme's background",
            popup.evaluate(
                "(c) => { const e = document.createElement('i'); e.style.color = c; document.body.append(e); return getComputedStyle(e).color }",
                site_background,
            )
            == background
            and paper == site_background,
            (background, paper, site_background),
        )
        popup.close()
    page.evaluate("document.documentElement.dataset.theme = 'dark'")

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

    # The case's facts are metadata, not a table of their own; the runs table counts attached files.
    page.goto(f"{BASE}/catalogue/solvers/vlasov-cpu-gpu/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    headings = page.locator(".sl-markdown-content h2").all_inner_texts()
    check(
        "the case's info is under Metadata",
        "Metadata" in headings and "Information" not in headings,
        headings,
    )
    check(
        "the metadata lists the case's commit",
        "commit" in page.locator(".meta-table").inner_text(),
    )
    check(
        "the runs table links the attached files",
        page.locator(".runs-table a[href$='#files']").count() == 2,
    )

    # CPU vs GPU: the GPU run has GPU timings, and both runs carry their files.
    page.goto(
        f"{BASE}/catalogue/solvers/vlasov-cpu-gpu/gpu-node/", wait_until="networkidle"
    )
    page.wait_for_timeout(1500)
    check(
        "the GPU run has GPU columns",
        page.locator("table.region-stats th[data-key=gpu_total]").count() == 1,
    )
    page.goto(
        f"{BASE}/catalogue/solvers/vlasov-cpu-gpu/cpu-node/", wait_until="networkidle"
    )
    page.wait_for_timeout(1500)
    check(
        "the CPU run has none",
        page.locator("table.region-stats th[data-key=gpu_total]").count() == 0,
    )
    check(
        "the run's metadata starts with the case's",
        page.locator(".meta-table tr").first.inner_text().startswith("commit"),
    )
    tabs = page.locator(".attached-files [role=tab]").all_inner_texts()
    check(
        "the case's script and the run's parameters are attached",
        tabs == ["run.py", "cpu-node.yml"],
        tabs,
    )
    check(
        "the attached code is shown highlighted",
        "ProfileManager" in page.locator(".attached-files").inner_text()
        and page.locator(".attached-files .expressive-code").count() >= 1,
    )
    href = page.locator(".attached-files a[download]").first.get_attribute("href")
    download = page.request.get(
        f"http://localhost:{BASE.split(':')[2].split('/')[0]}{href}"
    )
    check(
        "the attached file downloads",
        download.ok and "ProfileManager" in download.text(),
        href,
    )

    # A hybrid study offers every x-axis for its scaling charts.
    page.goto(f"{BASE}/catalogue/solvers/poisson-hybrid/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    hybrid = page.locator(
        ".chart-panel", has=page.locator("summary", has_text="Speedup")
    ).first
    check(
        "the x-axis can be ranks, nodes, threads or cores",
        hybrid.locator(".chart-axis").all_inner_texts()
        == ["MPI ranks", "nodes", "OpenMP threads", "MPI ranks × OpenMP threads"],
        hybrid.locator(".chart-axis").all_inner_texts(),
    )
    check(
        "the manifest's x-axis is the one it opens on",
        hybrid.locator(".chart-axis[aria-pressed=true]").inner_text()
        == "MPI ranks × OpenMP threads",
    )
    hybrid.locator(".chart-axis[data-axis='2']").click()
    page.wait_for_timeout(1500)
    check(
        "switching the axis redraws the chart",
        page.locator(".chart.js-plotly-plot").count() >= 1,
    )

    # Axis scales: log2 and log10 on a numeric axis; none on a categorical one.
    page.goto(f"{BASE}/catalogue/solvers/poisson-strong/", wait_until="networkidle")
    page.wait_for_timeout(2500)
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
    # Each scale control sits at its axis: the y one above the y axis, the x one past its right end.
    geometry = page.evaluate(
        f"""(() => {{
            const chart = document.getElementById('{chart_id}');
            const box = chart.getBoundingClientRect();
            const size = chart._fullLayout._size;
            const frame = chart.parentElement;
            return {{
                plotTop: box.top + size.t,
                plotLeft: box.left + size.l,
                plotRight: box.left + size.l + size.w,
                plotBottom: box.top + size.t + size.h,
                y: frame.querySelector('.axis-scale-y').getBoundingClientRect().toJSON(),
                x: frame.querySelector('.axis-scale-x').getBoundingClientRect().toJSON(),
            }};
        }})()"""
    )
    check(
        "the y scale sits beside the top of the y axis",
        abs(geometry["y"]["top"] - geometry["plotTop"]) < 6
        and geometry["y"]["right"] <= geometry["plotLeft"] + 1,
        geometry,
    )
    check(
        "the x scale sits past the end of the x axis",
        geometry["x"]["left"] >= geometry["plotRight"]
        and geometry["x"]["bottom"] <= geometry["plotBottom"] + 4,
        geometry["x"],
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
