"""Write a few small, synthetic scope-profiler files into ``data/``.

They let a fresh copy of this template build its site without any real profiling data. A fork
replaces this step with fetching its own files (see ``fetch_data.sh``).

The files are written with scope-profiler's own writer, from a made-up model of a solver that
scales well and of one whose communication grows with the rank count. One run, ``turbulence``, also
carries what a profile can hold beyond timings (tags, the source of a region, a line profile,
LIKWID counters and Linux perf events), so every section of the report pages has something to show.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scope_profiler.h5writer import ProfilingWriter
from scope_profiler.likwid_data import LikwidRegionResult
from scope_profiler.perf_events import PerfEventTotals
from scope_profiler.profile_manager import RankPayload

DATA = Path(__file__).resolve().parent.parent / "data"
MS = 1_000_000  # nanoseconds per millisecond

SOLVER_SOURCE = """\
def solve(u, rhs, omega=0.8):
    for _ in range(10):
        residual = rhs - apply_operator(u)
        u = u + omega * residual
    return u
"""


def _spans(calls):
    """``{name: (starts, ends)}`` as the int64 arrays the writer takes."""
    return {
        name: (np.array(starts, dtype=np.int64), np.array(ends, dtype=np.int64))
        for name, (starts, ends) in calls.items()
        if starts
    }


def _rank_calls(rank_jitter, ranks, solve_ms, comm_ms):
    """One rank's timeline: ``setup``, ten ``solve`` calls and the ``exchange`` after each."""
    names = ("session", "simulation", "setup", "solve", "exchange")
    calls = {name: ([], []) for name in names}
    setup = int(4 * MS)
    clock = 2 * MS
    calls["setup"][0].append(clock)
    calls["setup"][1].append(clock + setup)
    clock += setup
    for _ in range(10):
        work = int(solve_ms * MS * rank_jitter)
        calls["solve"][0].append(clock)
        calls["solve"][1].append(clock + work)
        clock += work
        if ranks > 1:
            wait = int(comm_ms * MS)
            calls["exchange"][0].append(clock)
            calls["exchange"][1].append(clock + wait)
            clock += wait
    calls["simulation"][0].append(2 * MS)
    calls["simulation"][1].append(clock)
    calls["session"][0].append(0)
    calls["session"][1].append(clock + 2 * MS)
    return {"scope_profiler.session": calls.pop("session"), **calls}


def _extras(solve_ns):
    """What the showcase run carries beyond its timings."""
    return {
        "tags": {"solve": ("physics", "hot")},
        "sources": {"solve": ("kernels/solver.py", 12, SOLVER_SOURCE)},
        "line_profile": [
            {
                "region": "solve",
                "filename": "kernels/solver.py",
                "function": "solve",
                "first_lineno": 12,
                "line_numbers": np.array([13, 14, 15, 16]),
                "hits": np.array([10, 10, 10, 10]),
                "times": np.array([3.0, 60.0, 31.0, 6.0]) * solve_ns / 100.0,
                "unit": 1e-9,
                "source": SOLVER_SOURCE.rstrip("\n"),
                "source_first_lineno": 12,
            }
        ],
        "likwid": {
            "solve": LikwidRegionResult(
                tag="solve",
                group_id=0,
                group_name="FLOPS_DP",
                cpus=[0],
                times=np.asarray([solve_ns * 1e-9]),
                call_counts=np.asarray([10]),
                event_names=[
                    "INSTR_RETIRED_ANY",
                    "CPU_CLK_UNHALTED_CORE",
                    "FP_ARITH_INST_RETIRED_256B_PACKED_DOUBLE",
                ],
                counter_names=["FIXC0", "FIXC1", "PMC0"],
                events=np.asarray([[4.2e9, 3.1e9, 6.5e8]]),
                metric_names=["CPI", "DP [MFLOP/s]"],
                metrics=np.asarray([[0.74, 5200.0]]),
                source="full_api",
            )
        },
        "perf_events": {
            "solve": PerfEventTotals(
                calls=10,
                values={
                    "cycles": 3_100_000_000,
                    "instructions": 4_200_000_000,
                    "cache-misses": 1_800_000,
                },
            )
        },
    }


def write_run(path: Path, ranks: int, *, solve_ms: float, comm_ms: float, seed: int, extras=False):
    """Write one run of ``ranks`` ranks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    metadata = {
        "mpi_size": ranks,
        "omp_num_threads": 1,
        "num_nodes": max(1, math.ceil(ranks / 4)),
        "total_cores": ranks,
        "timestamp": "2026-10-17T12:00:00Z",
        "scope_profiler_version": "sample",
        "platform": "synthetic",
        "chip_information": "synthetic CPU",
    }
    with ProfilingWriter(path, metadata) as writer:
        for rank in range(ranks):
            jitter = 1.0 + 0.04 * rng.standard_normal()
            payload = {}
            if extras and rank == 0:
                payload = _extras(int(solve_ms * MS * 10 * jitter))
            writer.write_rank(
                rank,
                RankPayload(
                    regions=_spans(_rank_calls(jitter, ranks, solve_ms, comm_ms)),
                    likwid=payload.get("likwid", {}),
                    likwid_environment={},
                    perf_events=payload.get("perf_events"),
                    sources=payload.get("sources"),
                    tags=payload.get("tags"),
                    line_profile=payload.get("line_profile"),
                ),
            )


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
    write_run(DATA / "turbulence" / "np1.h5", 1, solve_ms=90.0, comm_ms=0.0, seed=200, extras=True)
    print(f"Wrote {len(list(DATA.rglob('*.h5')))} sample files to {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
