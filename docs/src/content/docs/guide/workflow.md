---
title: Data and the workflow
description: Where the profiling files come from and how the site is built and deployed.
---

## The pipeline

The docs workflow (`.github/workflows/docs.yml`) uses the shared workflow of the max-models
docs sites. Before it builds the site it runs, in the repository root,

```bash
bash scripts/fetch_data.sh && uv run scope-profiler site catalogue.yaml -o docs
```

1. `scripts/fetch_data.sh` puts the profiling files into `data/`.
2. `scope-profiler site` reads `catalogue.yaml` and writes the pages and chart data into
   `docs/src/content/docs/catalogue/` and `docs/public/catalogue/`.
3. The site is built (`astro build`, with an MDX check, a link check and a search index) and
   deployed to GitHub Pages. The workflow also checks that the deployed site answers.

## Getting the files

The files should not be committed to this repository: they are large and change often. Fetch
them in `scripts/fetch_data.sh` from wherever your runs end up, for example

- a data repository: `git clone --depth 1 https://github.com/my-org/profiling-data data`
- release assets: `gh release download --repo my-org/my-code --pattern '*.h5' --dir data`
- a bucket: `aws s3 sync s3://my-bucket/profiling data`

The shared workflow passes no secrets to the build, so the files have to be readable without
one (a public repository, public release assets, a public bucket). For private data, build the
site in your own workflow instead and call the shared one's steps from there.

## Updating the catalogue

A new run is a new file and a line (or a glob) in `catalogue.yaml`. A scheduled or
`repository_dispatch` workflow in the data repository can trigger this repository's docs
workflow (`workflow_dispatch`) after it has uploaded new files, so the catalogue follows the
data.

## Versions

`docs/package.json` and `.github/workflows/docs.yml` pin the theme version, and `pyproject.toml`
the scope-profiler version that has `scope-profiler site`. The charts are drawn with the
`@scope-profiler/plotly` package; use a version that supports the plot-data format your
scope-profiler writes.
