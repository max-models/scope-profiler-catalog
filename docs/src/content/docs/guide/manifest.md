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
| `charts: false` | Pages and tables only for this case. |

The keys `scaling`, `speedup_x`, `include`, `exclude`, `ranks` and `charts` can also be set once
under `defaults`. The whole manifest is checked before anything is written, and an error names
the case and field.

The full reference is in the
[scope-profiler documentation](https://max-models.github.io/scope-profiler/cli/#scope-profiler-site).
Only metadata that identifies a run is published (time, platform, versions, threads, ranks,
nodes), never the host name, user or environment.
