---
title: A section of your docs
description: Put a code's profiling catalogue into its own documentation site instead of a site of its own.
---

A catalogue does not need a site of its own. `scope-profiler site --section profiling` writes the
same pages into `src/content/docs/profiling/` of any Astro/Starlight site, so a code's
documentation can carry a "Profiling" section next to its guides and API reference. The
components that draw the pages ship with scope-profiler and are copied in on every run.

## The results repository

Keep the profiling files out of the code's repository: one repository of results serves every
code. [`scope-profiler jobs`](https://max-models.github.io/scope-profiler/guide/jobs/) uploads
each case it runs into it, into a directory of the code's own:

```toml
# profiling/heat.toml, run on a cluster with `scope-profiler jobs run profiling/heat.toml --upload`
[case]
label = "heat"
name = "Heat equation, strong scaling"
command = ["python", "heat.py", "--profile-out", "{profile}"]
inputs = ["heat.py"]

[[launch]]
ntasks = 1
[[launch]]
ntasks = 4

[store]
url = "git@github.com:my-org/profiling-results.git"
path = "mycode/{label}"   # mycode/heat/<timestamp>-<commit>-heat/run01/profiling_data.h5
```

## In the code's repository

1. A manifest, `profiling/profiling.yaml`, whose cases find their executions in the results:

   ```yaml
   title: Profiling
   description: Profiling runs of mycode.
   base: /mycode   # the docs site's base path
   cases:
     - id: heat
       title: Heat equation, strong scaling
       executions:
         path: "data/mycode/heat/{execution}/run*/profiling_data.h5"
   ```

   Every uploaded case folder becomes an execution, named by its date and commit, so new runs
   need no change here.

2. `profiling/fetch_data.sh`, which fetches only the code's directory of the results:

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   cd "$(dirname "$0")"
   rm -rf data
   git clone -q --depth 1 --filter=blob:none --sparse https://github.com/my-org/profiling-results data
   git -C data sparse-checkout set mycode
   ```

3. The Python packages: `scope-profiler[pproc,site]` in the `docs` extra of `pyproject.toml`.

4. In `docs/`: the npm packages the components import,

   ```bash
   npm install @scope-profiler/plotly plotly.js-dist-min
   ```

   the generated directories in `docs/.gitignore`,

   ```text
   src/content/docs/profiling/
   public/profiling/
   src/components/scope-profiler/
   ```

   and a sidebar group (and a nav entry) in `docs/astro.config.mjs`:

   ```js
   nav: [/* ... */ { label: 'Profiling', link: '/profiling/' }],
   sidebar: [
   	/* ... */
   	{ label: 'Profiling', items: [{ autogenerate: { directory: 'profiling', collapsed: true } }] },
   ],
   ```

5. The pages, written before the site is built: in the docs workflow,

   ```yaml
   pre-build: >-
     bash profiling/fetch_data.sh &&
     uv run --extra docs scope-profiler site profiling/profiling.yaml -o docs --section profiling
   ```

   and locally a Makefile target that does the same before `docs-dev` and `docs-build`.

The section then has an overview of the cases and a page per case, its executions and its runs,
exactly as a catalogue site of its own.
