---
title: The manifest
description: How catalogue.yaml describes the cases and runs of a catalogue.
---

`catalogue.yaml` lists the *cases* of the catalogue. A case is a set of runs that belong
together, such as one problem at several MPI rank counts. The file is read by
`scope-profiler site`; paths in it are relative to the file.

```yaml
title: Profiling runs of my code
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
    files: [scripts/run.py]     # attached to every run of the case
    runs:
      - {path: data/np1.h5, label: 1 rank, files: [params/np1.yml]}
      - {path: "data/np*.h5", files: ["params/{stem}.yml"]}   # globs, in natural order (np2 before np10)
```

| Key | Meaning |
| --- | --- |
| `base` | The base path of the site, the same as `repo` in `docs/astro.config.mjs` with a `/` before it (`""` for a site at the root of a domain). The links between pages need it. |
| `id` | The page name of the case; unique. Defaults to the slug of `title`. |
| `group` | Nests the case in a sidebar group of that name. |
| `tags` | Shown on the index and on the case page. |
| `scaling` | `strong` draws the speedup of runs of different sizes, `weak` the weak-scaling efficiency, `both` both, `none` neither. |
| `speedup_x` | What the speedup is plotted over; `auto` takes the one the runs differ in. |
| `info` | Free-form facts about the case, such as the commit, shown as metadata: at the end of the case page and ahead of each run's own metadata. They are not read from the profiles, which do not record one. Quote values YAML would read as numbers or dates: `commit: "0000000"`. |
| `files` | Scripts and parameter files attached to a run (under a run) or to every run of the case (under the case). Paths and globs are relative to the manifest; in a glob of runs, `{stem}` is the run file's name without its extension, so `params/{stem}.yml` names each run's own file. Each is shown on the run's page with syntax highlighting, and offered for download. Text files up to 200 kB are shown; larger or binary ones are only offered for download. |
| `runs` | The profiling files (`.h5`, `.json`, `.json.gz`). A `label` names a run; otherwise the label recorded in the file, or its name. |
| `executions` | Instead of `runs`, for a case that is run again and again (a nightly job): a list of `{id, label, date, info, runs}`, or a pattern, `path: data/nightly/{execution}/np*.h5`, that finds one execution per directory (an optional `meta.yml` in it gives the `label`, `date` and `info`). The case page is the latest execution (by `date`, else the last listed), with a table of the executions and a chart of each run's wall time over them; every earlier execution has a page of its own, linked from that table. A page of its own compares any two runs, of the same execution or of different ones (it opens on the biggest run the newest two executions share). A run is followed over the executions by the MPI ranks it ran on (ranks and OpenMP threads, or else its label, when an execution has two runs on as many ranks). |
| `images` | Images (png, jpg, gif, webp, svg) and PDFs: under a run, for its page (`{stem}` works as for `files`); under the case, for the case page. Shown as a grid of previews that open in a lightbox. |
| `code` | Code shown at the bottom of the case page: each entry a path (shown with syntax highlighting), a link `url`, or both, with an optional `label`. |
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
  show every run against the baseline (the box is unticked by default). The duration, rank
  imbalance and rank heatmap charts of several runs draw only the compared runs. The scaling
  charts' x-axis can be MPI ranks, nodes, OpenMP threads or their product, for the axes the runs
  differ in; `speedup_x` picks the one a case opens on. A run's durations chart has a "stack
  children" checkbox (the `--stack-children` of `scope-profiler plot durations`), which splits
  each bar into the region's own time and one segment per region it calls directly.

The sidebar lists each case once; a case page lists its runs, and a run page links the runs either
side of it. Every chart has linear, log2 and log10 scales for its numeric axes.

Unless the case sets `metadata: all`, only metadata that identifies a run is published, never the
host name, user or environment.

The full reference is in the
[scope-profiler documentation](https://max-models.github.io/scope-profiler/cli/#scope-profiler-site).
