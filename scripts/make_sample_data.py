"""Write a few small, synthetic scope-profiler files into ``data/``.

They let a fresh copy of this template build its site without any real profiling
data. A fork replaces this step with fetching its own files (see ``fetch_data.sh``).

The files follow the HDF5 layout of scope-profiler: run metadata as attributes of a
``metadata`` group, and, per rank, the start and end time of every call of every
region in nanoseconds. The numbers come from a made-up model of a solver that scales
well and of one whose communication grows with the rank count.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import h5py
import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
MS = 1_000_000  # nanoseconds per millisecond


def write_run(path: Path, ranks: int, *, solve_ms: float, comm_ms: float, seed: int):
    """One run: ``simulation`` holds ``setup``, ten ``solve`` calls and ``exchange``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    with h5py.File(path, "w") as h5file:
        metadata = h5file.create_group("metadata")
        for key, value in {
            "mpi_size": ranks,
            "omp_num_threads": 1,
            "num_nodes": max(1, math.ceil(ranks / 4)),
            "total_cores": ranks,
            "timestamp": "2026-10-17T12:00:00Z",
            "scope_profiler_version": "sample",
            "platform": "synthetic",
        }.items():
            metadata.attrs[key] = value
        for rank in range(ranks):
            jitter = 1.0 + 0.04 * rng.standard_normal()
            calls: dict[str, tuple[list[int], list[int]]] = {
                "simulation": ([], []),
                "setup": ([], []),
                "solve": ([], []),
                "exchange": ([], []),
            }
            clock = 0
            setup = int(4 * MS)
            calls["setup"][0].append(clock)
            calls["setup"][1].append(clock + setup)
            clock += setup
            for _ in range(10):
                work = int(solve_ms * MS * jitter)
                calls["solve"][0].append(clock)
                calls["solve"][1].append(clock + work)
                clock += work
                if ranks > 1:
                    wait = int(comm_ms * MS)
                    calls["exchange"][0].append(clock)
                    calls["exchange"][1].append(clock + wait)
                    clock += wait
            calls["simulation"][0].append(0)
            calls["simulation"][1].append(clock)
            regions = h5file.create_group(f"rank{rank}").create_group("regions")
            for name, (starts, ends) in calls.items():
                if not starts:
                    continue
                region = regions.create_group(name)
                region.create_dataset("start_times", data=np.array(starts, "int64"))
                region.create_dataset("end_times", data=np.array(ends, "int64"))


def main() -> int:
    DATA.mkdir(exist_ok=True)
    for ranks in (1, 2, 4, 8):
        # Strong scaling: the same problem on more ranks.
        write_run(
            DATA / "poisson-strong" / f"np{ranks}.h5",
            ranks,
            solve_ms=40.0 / ranks,
            comm_ms=0.5 * math.log2(ranks),
            seed=ranks,
        )
        # Weak scaling: the problem grows with the ranks, so the solve time is flat
        # and the communication is what grows.
        write_run(
            DATA / "advection-weak" / f"np{ranks}.h5",
            ranks,
            solve_ms=12.0,
            comm_ms=1.5 * math.log2(ranks),
            seed=100 + ranks,
        )
    write_run(DATA / "turbulence" / "np1.h5", 1, solve_ms=90.0, comm_ms=0.0, seed=200)
    print(f"Wrote {len(list(DATA.rglob('*.h5')))} sample files to {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
