---
title: The manifest
description: How catalogue.yaml describes the cases and runs of a catalogue.
---

`catalogue.yaml` lists the *cases* of the catalogue. A case is a set of runs that belong
together, such as one problem at several MPI rank counts. The file is read by
`scope-profiler site`; paths in it are relative to the file.

```yaml
title: Struphy profiling
description: Profiling runs of the Poisson solver.
base: /my-catalogue             # "/" plus the repository name
defaults: {scaling: strong, speedup_x: auto}
cases:
  - id: poisson-cube            # default: the slug of the title
    title: Poisson cube, strong scaling
    description: The solver on a 256^3 cube.
    group: Poisson              # optional: a sidebar group
    tags: [cpu, scaling]
    scaling: strong             # strong, weak, both or none
    speedup_x: auto             # auto, ranks, nodes, threads or cores
    info: {commit: 843a82cd, date: 2026-10-16}
    runs:
      - {path: data/np1.h5, label: 1 rank}
      - {path: "data/np*.h5"}   # globs, in natural order (np2 before np10)
```

| Key | Meaning |
| --- | --- |
| `base` | The base path of the site, the same as `repo` in `docs/astro.config.mjs` with a `/` before it (`""` for a site at the root of a domain). The links between pages need it. |
| `id` | The page name of the case; unique. Defaults to the slug of `title`. |
| `group` | Nests the case in a sidebar group of that name. |
| `tags` | Shown on the index and on the case page. |
| `scaling` | `strong` draws the speedup of runs of different sizes, `weak` the weak-scaling efficiency, `both` both, `none` neither. |
| `speedup_x` | What the speedup is plotted over; `auto` takes the one the runs differ in. |
| `info` | Free-form facts shown on the case page, such as the commit. They are not read from the profiles, which do not record one. Quote values YAML would read as numbers or dates: `commit: "0000000"`. |
| `runs` | The profiling files (`.h5`, `.json`, `.json.gz`). A `label` names a run; otherwise the label recorded in the file, or its name. |
| `include`, `exclude`, `ranks` | Which regions and MPI ranks the pages show. |
| `metadata` | `minimal` (the default) publishes only what identifies a run (time, platform, chip, versions, threads, ranks, nodes); `all` publishes every metadata field the profile recorded, host name and environment included. |
| `charts: false` | Pages and tables only for this case. |

The keys `scaling`, `speedup_x`, `include`, `exclude`, `ranks` and `charts` can also be set once
under `defaults`. The whole manifest is checked before anything is written, and an error names
the case and field.

## What the pages show

Every page has everything `scope-profiler report` shows, with a filter bar at the top that
filters the regions of every table and chart, and a click on a region highlights it everywhere.

- A **run page** has the headline numbers and findings, the ranked hotspots, the region
  statistics table (the call tree, sortable columns and trend lines; click a row for its call
  site, tags, per-rank breakdown and line profile), the load balance and rank comparison of runs
  on several ranks, the line profiles of regions outside the table, hardware counters, the
  charts and the metadata.
- A **case page** of several runs has the runs table, what changed between two runs (the largest
  improvements and regressions), the durations table of every region in them (switch between total,
  own and per-call time and calls, in call-tree order or by the size of the change) and the
  speedup, weak-scaling, change and duration charts. A study can have hundreds of runs, so you
  **pick the two runs to compare**, a baseline and a candidate; the choice is kept in the URL
  (`?base=np4&cand=np64`), so a comparison can be shared. A study of up to twelve runs can also
  show every run against the baseline.

The sidebar lists each case once; a case page lists its runs, and a run page links the runs either
side of it. Every chart has linear, log2 and log10 scales for its numeric axes.

Unless the case sets `metadata: all`, only metadata that identifies a run is published, never the
host name, user or environment.

The full reference is in the
[scope-profiler documentation](https://max-models.github.io/scope-profiler/cli/#scope-profiler-site).
