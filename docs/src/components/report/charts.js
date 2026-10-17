// Draws the report's chart panels with @scope-profiler/plotly: a port of the standalone report's
// chart module. The panels follow the page's region filter (scopeProfilerOnRegionFilter), the
// Regions and Depth sliders, and the highlighted region (scopeProfilerOnRegionSelect), all
// provided by client.js; a click on a chart highlights the region it shows.
import { buildComparisonFigure, buildFigure } from '@scope-profiler/plotly';

const root = document.getElementById('sp-charts');

if (root) {
	const regionIndex = JSON.parse(root.dataset.regionIndex || '{}');
	const charts = [...root.querySelectorAll('.chart')].map((element) => ({
		id: element.id,
		element,
		title: element.dataset.title,
		options: JSON.parse(element.dataset.options || '{}'),
		variants: element.dataset.variants ? JSON.parse(element.dataset.variants) : null,
		src: element.dataset.src,
		payload: null,
		figure: null,
		stale: false,
	}));
	let plotly = null;

	const theme = () => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');

	const payloadRegions = (payload) => {
		const rows = [
			...(payload.intervals ?? []),
			...(payload.bars ?? []),
			...(payload.points ?? []),
			...(payload.calls ?? []),
			...(payload.regions ?? []),
		];
		return new Set(rows.map((row) => row.region ?? row.name).filter(Boolean));
	};

	const traceMatchesRegion = (trace, region) => {
		const name = String(trace.name ?? '');
		return (
			name === region ||
			name.endsWith(` / ${region}`) ||
			name === `${region} mean` ||
			name.endsWith(` / ${region} mean`)
		);
	};

	const highlightFigure = (chart, figure, region) => {
		if (!region || !payloadRegions(chart.payload).has(region)) return figure;
		for (const trace of figure.data) {
			if (trace.type === 'icicle') {
				const labels = trace.labels ?? [];
				const original = Array.isArray(trace.marker?.colors) ? trace.marker.colors : [];
				trace.marker.colors = labels.map((label, index) =>
					label === region ? (original[index] ?? '#d97706') : 'rgba(156,163,175,0.22)',
				);
			} else if (trace.type === 'heatmap') {
				figure.layout.shapes = [
					...(figure.layout.shapes ?? []),
					{
						type: 'rect',
						xref: 'x',
						yref: 'paper',
						x0: region,
						x1: region,
						x0shift: -0.5,
						x1shift: 0.5,
						y0: 0,
						y1: 1,
						fillcolor: 'rgba(245,158,11,0.16)',
						line: { color: '#d97706', width: 3 },
					},
				];
			} else if (trace.type === 'bar' && trace.orientation === 'h') {
				trace.opacity = traceMatchesRegion(trace, region) ? 1 : 0.16;
			} else if (trace.type === 'bar') {
				trace.marker.opacity = (trace.x ?? []).map((value) => (value === region ? 1 : 0.16));
				trace.marker.line = {
					...(trace.marker.line ?? {}),
					color: (trace.x ?? []).map((value) => (value === region ? '#92400e' : 'rgba(0,0,0,0.12)')),
					width: (trace.x ?? []).map((value) => (value === region ? 2 : 0.5)),
				};
			} else if (trace.type === 'scatter') {
				trace.opacity = traceMatchesRegion(trace, region) ? 1 : 0.14;
			}
		}
		return figure;
	};

	const regionFromPoint = (chart, point) => {
		const regions = payloadRegions(chart.payload);
		const identity = point.customdata?.identity;
		if (identity && regions.has(identity.region)) return identity.region;
		for (const candidate of [point.label, point.x, point.y, point.data?.name]) {
			if (regions.has(candidate)) return candidate;
		}
		const traceName = String(point.data?.name ?? '');
		for (const region of regions) {
			if (
				traceName === `${region} mean` ||
				traceName.endsWith(` / ${region}`) ||
				traceName.endsWith(` / ${region} mean`)
			) {
				return region;
			}
		}
		return null;
	};

	const runFromPoint = (chart, point, region) => {
		if (point.customdata?.identity?.file != null) return point.customdata.identity.file;
		if (Array.isArray(point.customdata) && typeof point.customdata[0] === 'string') {
			return point.customdata[0];
		}
		const name = String(point.data?.name ?? '');
		return region && name.endsWith(` / ${region}`) ? name.slice(0, -region.length - 3) : null;
	};

	let activeTerms = [];
	let selectedRegion = null;
	const termFilter = (region) =>
		activeTerms.some((term) =>
			term.startsWith('^')
				? String(region).toLowerCase().startsWith(term.slice(1))
				: String(region).toLowerCase().includes(term),
		);

	// The filter bar's Regions and Depth sliders limit every chart to the same regions: those no
	// deeper than maxDepth, then the topN of them by time. The timeline also hides the deeper calls
	// of the regions it keeps.
	const regionLimits = {};
	let limitedRegions = null;
	const limitedSet = () => {
		const { topN, maxDepth } = regionLimits;
		let names = Object.keys(regionIndex).filter((name) => {
			const depth = regionIndex[name][1];
			return (
				(!activeTerms.length || termFilter(name)) && (maxDepth == null || depth == null || depth <= maxDepth)
			);
		});
		if (topN != null) {
			names = names.sort((a, b) => regionIndex[b][0] - regionIndex[a][0]).slice(0, topN);
		}
		return new Set(names);
	};
	const updateLimitedRegions = () => {
		limitedRegions = Object.keys(regionLimits).length ? limitedSet() : null;
		window.scopeProfilerSetRegionLimit?.(limitedRegions);
	};
	const chartFilter = (region) =>
		(!activeTerms.length || termFilter(region)) && (!limitedRegions || limitedRegions.has(region));

	async function ensurePayload(chart) {
		if (!chart.payload) {
			const response = await fetch(chart.src);
			if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
			chart.payload = await response.json();
		}
	}

	async function draw(chart) {
		const target = chart.element;
		// A chart in a collapsed panel waits until the panel opens: a timeline of hundreds of lanes is
		// seconds of drawing that nobody may look at.
		const panel = target.closest('details');
		if (panel && !panel.open) {
			chart.stale = true;
			return;
		}
		chart.stale = false;
		try {
			await ensurePayload(chart);
			plotly ??= (await import('plotly.js-dist-min')).default;
			let options =
				activeTerms.length || limitedRegions ? { ...chart.options, filterRegion: chartFilter } : chart.options;
			if (chart.payload.plot === 'gantt' && regionLimits.maxDepth != null) {
				options = { ...options, maxDepth: regionLimits.maxDepth };
			}
			// buildFigure dispatches region_statistics to the ranked summary; only buildComparisonFigure
			// draws the signed per-region change.
			const build = options.comparison ? buildComparisonFigure : buildFigure;
			const { layout: extra, ...rest } = options;
			const figure = highlightFigure(chart, build(chart.payload, { ...rest, layout: extra, theme: theme() }), selectedRegion);
			figure.layout = { ...figure.layout, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' };
			chart.figure = figure;
			target.classList.remove('chart-error');
			const rendered = plotly.react(target, figure.data, figure.layout, { responsive: true, displaylogo: false });
			if (!target.dataset.regionClickBound) {
				target.dataset.regionClickBound = 'true';
				Promise.resolve(rendered).then(() =>
					target.on('plotly_click', (event) => {
						const point = event.points?.[0];
						if (!point) return;
						const region = regionFromPoint(chart, point);
						if (region && typeof window.scopeProfilerSelectRegion === 'function') {
							// "toast": highlight in place, and offer the jump to the table rather than scrolling
							// away from the chart being explored.
							window.scopeProfilerSelectRegion(region, runFromPoint(chart, point, region), 'toast');
						}
					}),
				);
			}
		} catch (error) {
			target.classList.add('chart-error');
			target.textContent = `Could not render chart: ${error.message}`;
		}
	}

	const redraw = () => {
		updateLimitedRegions();
		for (const chart of charts) draw(chart);
	};
	// Both hooks call their listener as soon as it registers, which would draw every chart twice on
	// load; changes arriving together are drawn once.
	let redrawQueued = false;
	const scheduleRedraw = () => {
		if (redrawQueued) return;
		redrawQueued = true;
		queueMicrotask(() => {
			redrawQueued = false;
			redraw();
		});
	};

	for (const chart of charts) {
		const panel = chart.element.closest('details');
		panel?.addEventListener('toggle', () => {
			if (!panel.open) return;
			if (chart.stale || !chart.figure) draw(chart);
			else plotly?.Plots.resize(chart.element);
		});
	}

	// Redraw on a switch between light and dark.
	new MutationObserver(scheduleRedraw).observe(document.documentElement, {
		attributes: true,
		attributeFilter: ['data-theme'],
	});

	for (const button of document.querySelectorAll('[data-chart-action]')) {
		button.addEventListener('click', () => {
			const open = button.dataset.chartAction === 'expand';
			for (const panel of root.querySelectorAll('details.chart-panel')) panel.open = open;
		});
	}

	// "Open in new tab": the chart as drawn, filter and highlight included, on a page of its own,
	// sized to the window, with the Plotly runtime from its CDN.
	const escapeHtml = (value) =>
		String(value).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
	const openInNewTab = (chart) => {
		if (!chart.figure) return;
		const version = root.dataset.plotlyVersion;
		const figure = JSON.stringify({ data: chart.figure.data, layout: chart.figure.layout }).replace(/</g, '\\u003c');
		const page = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(chart.title)}</title><style>html, body { margin: 0; background: #fff; }
#chart { width: 100vw; }</style></head><body><div id="chart"></div>
<script crossorigin="anonymous" src="https://cdn.plot.ly/plotly-${escapeHtml(version)}.min.js"><\/script><script>
const figure = ${figure};
const target = document.getElementById("chart");
const layout = { ...figure.layout, autosize: true, paper_bgcolor: "#fff", plot_bgcolor: "#fff",
  title: figure.layout.title ?? { text: ${JSON.stringify(escapeHtml(chart.title))} } };
delete layout.width;
if (!(layout.height > window.innerHeight)) { delete layout.height; target.style.height = "100vh"; }
Plotly.newPlot(target, figure.data, layout, { responsive: true, displaylogo: false });
<\/script></body></html>`;
		const url = URL.createObjectURL(new Blob([page], { type: 'text/html' }));
		window.open(url, '_blank');
		setTimeout(() => URL.revokeObjectURL(url), 60000);
	};
	for (const button of document.querySelectorAll('.chart-open')) {
		const chart = charts.find((item) => item.id === button.dataset.chart);
		if (chart) button.addEventListener('click', () => openInNewTab(chart));
	}

	// At its maximum a slider means all. The readout follows the thumb, while the charts, which can
	// take most of a second to draw, wait for it to rest.
	const topLabel = (value, max) => (value >= max ? `all ${max}` : `top ${value} of ${max}`);
	const depthLabel = (value, max) =>
		value >= max
			? 'all levels'
			: value === 0
				? 'top level only'
				: `${value} level${value > 1 ? 's' : ''} of children`;
	for (const slider of document.querySelectorAll('.region-top, .region-depth')) {
		const isTop = slider.classList.contains('region-top');
		const key = isTop ? 'topN' : 'maxDepth';
		const readout = slider.nextElementSibling;
		const read = () => {
			const value = Number(slider.value);
			if (value >= Number(slider.max)) delete regionLimits[key];
			else regionLimits[key] = value;
		};
		// The page opens on the slider's own value: past 500 regions, the top 500.
		read();
		let timer = null;
		const apply = () => {
			window.clearTimeout(timer);
			const before = regionLimits[key];
			read();
			if (regionLimits[key] !== before) scheduleRedraw();
		};
		slider.addEventListener('input', () => {
			const value = Number(slider.value);
			const max = Number(slider.max);
			readout.textContent = isTop ? topLabel(value, max) : depthLabel(value, max);
			window.clearTimeout(timer);
			timer = window.setTimeout(apply, 150);
		});
		slider.addEventListener('change', apply);
	}

	// The scaling charts' x-axis buttons: each swaps in the data computed for that axis, and the
	// description's axis name with it.
	for (const button of document.querySelectorAll('.chart-axis')) {
		const chart = charts.find((item) => item.id === button.dataset.chart);
		const variant = chart?.variants?.[Number(button.dataset.axis)];
		if (!variant) continue;
		button.addEventListener('click', async () => {
			chart.src = variant.src;
			chart.payload = null;
			const panel = button.closest('.chart-panel');
			for (const other of panel.querySelectorAll('.chart-axis')) {
				other.setAttribute('aria-pressed', String(other === button));
			}
			for (const label of panel.querySelectorAll('[data-axis-label]')) {
				label.textContent = variant.label;
			}
			draw(chart);
		});
	}

	if (typeof window.scopeProfilerOnRegionFilter === 'function') {
		window.scopeProfilerOnRegionFilter((terms) => {
			activeTerms = terms;
			scheduleRedraw();
		});
	}
	if (typeof window.scopeProfilerOnRegionSelect === 'function') {
		window.scopeProfilerOnRegionSelect((region) => {
			selectedRegion = region;
			scheduleRedraw();
		});
	}
	if (typeof window.scopeProfilerOnRegionFilter !== 'function' && typeof window.scopeProfilerOnRegionSelect !== 'function') {
		scheduleRedraw();
	}
}
