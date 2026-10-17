---
title: Use this template
description: Fork the template, describe your runs and publish a profiling catalogue.
---

This repository is a template, not a library: it is not published to PyPI. A code such as
struphy or gvec forks it once and keeps it as the home of its profiling results.

## 1. Fork it

Create a repository from this template (or fork it). In the new repository:

1. In `docs/astro.config.mjs`, set `repo` to the repository's name, `owner` if it is not
   `max-models`, and the `title` and `description`. The base path of the site follows from
   `repo`.
2. In `catalogue.yaml`, set `base` to `/` plus the same name. The generated pages need the base
   path for their links, because the site's link check rejects relative ones.
3. In `pyproject.toml`, rename the project.
4. Enable GitHub Pages with the source **GitHub Actions** (Settings, Pages).

## 2. Describe your runs

Write `catalogue.yaml`: [the manifest](/scope-profiler-catalog/guide/manifest/) lists the cases and the profiling files of
each. Check it with

```bash
uv run scope-profiler site catalogue.yaml --check
```

## 3. Get the files

`scripts/fetch_data.sh` puts the files into `data/` before the site is built. In the template it
writes synthetic samples with `scripts/make_sample_data.py`; replace it with the way your files
reach the repository, and delete the sample script. See [data and the workflow](/scope-profiler-catalog/guide/workflow/).

## 4. Build it

```bash
make install    # uv sync with the docs extra
make docs-dev   # fetches the data, writes the pages, serves http://localhost:4321/scope-profiler-catalog/
```

Push to `devel` and the docs workflow builds the site and deploys it.

## What stays the same

The pages in `docs/src/content/docs/catalogue/` and the chart data in `docs/public/catalogue/`
are generated and ignored by git; everything else is yours to change, including the
`ScopeChart` component in `docs/src/components/` that draws the charts.
