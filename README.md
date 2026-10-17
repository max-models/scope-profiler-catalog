# scope-profiler-catalog

[![Docs](https://github.com/max-models/scope-profiler-catalog/actions/workflows/docs.yml/badge.svg)](https://max-models.github.io/scope-profiler-catalog/)
[![Static analysis](https://github.com/max-models/scope-profiler-catalog/actions/workflows/static_analysis.yml/badge.svg)](https://github.com/max-models/scope-profiler-catalog/actions/workflows/static_analysis.yml)

A template for **profiling catalogue websites**: every profiling run of a code, in one
searchable [Astro](https://astro.build/) + [Starlight](https://starlight.astro.build/) site that
uses the same theme as the other max-models projects. It is not a Python package and is not
published to PyPI.

Site: <https://max-models.github.io/scope-profiler-catalog/>

How it works:

1. `catalogue.yaml` lists the *cases* of the catalogue and the
   [scope-profiler](https://github.com/max-models/scope-profiler) files of each.
2. `scripts/fetch_data.sh` puts those files into `data/` (in the template, synthetic samples).
3. `scope-profiler site catalogue.yaml -o docs` writes a page per case and per run, with charts,
   hotspot tables and scaling plots, into the Astro project in `docs/`.
4. The docs workflow builds the site and deploys it to GitHub Pages.

## Use it

Create a repository from this template, set `repo` (and `title`) in `docs/astro.config.mjs`,
describe your runs in `catalogue.yaml`, replace the body of `scripts/fetch_data.sh` with the way
your files arrive, and enable GitHub Pages (source: GitHub Actions). The guide on the site goes
through it step by step.

## Develop

```bash
make install     # uv sync, the npm packages, the pre-commit hooks
make check       # validate catalogue.yaml and the files it lists
make docs-dev    # fetch the data, write the pages, serve http://localhost:4321/scope-profiler-catalog/
make docs-build  # the static site in docs/dist, as in CI
```

Run `make help` for all targets. The pages in `docs/src/content/docs/catalogue/` and the chart data
in `docs/public/catalogue/` are generated and ignored by git.
