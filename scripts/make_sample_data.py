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


RUN_SCRIPT = """\
\"\"\"Landau damping of a Langmuir wave with a Vlasov-Ampere solver: the script both runs use.\"\"\"

import sys

import yaml
from scope_profiler import ProfileManager


def main(parameter_file):
    with open(parameter_file) as handle:
        parameters = yaml.safe_load(handle)
    with ProfileManager.session(label=parameters["label"]):
        with ProfileManager.region("setup"):
            state = initialise(parameters)
        for _ in range(parameters["steps"]):
            with ProfileManager.region("solve"):
                state = advance(state, parameters["dt"])
            with ProfileManager.region("exchange"):
                exchange_halos(state)


if __name__ == "__main__":
    main(sys.argv[1])
"""

PARAMETERS = """\
# Landau damping of a Langmuir wave, k = 0.5, 1 percent perturbation
label: {device} node
device: {device}
mpi_ranks: {ranks}
omp_threads: {threads}
steps: 10
dt: 0.05
grid:
  cells: [128, 128, 128]
  particles_per_cell: 128000
"""


def _density_figure(name: str, color: str, peak: float) -> str:
    """A small SVG line plot, standing in for a figure a simulation wrote beside its profile."""
    points = " ".join(
        f"{40 + 5.2 * i:.1f},{150 - 110 * peak * math.exp(-0.5 * ((i - 25) / 7) ** 2) * (1 + 0.1 * math.cos(i / 2)):.1f}"
        for i in range(51)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" font-family="sans-serif" font-size="10">'
        '<rect width="320" height="180" fill="white"/>'
        '<path d="M40 150H300M40 150V20" stroke="#444" fill="none"/>'
        f'<polyline points="{points}" stroke="{color}" stroke-width="2" fill="none"/>'
        f'<text x="170" y="14" text-anchor="middle">Density profile, {name}</text>'
        '<text x="170" y="172" text-anchor="middle">x</text></svg>\n'
    )


def _spans(calls, gpu=None):
    """``{name: (starts, ends)}`` as the int64 arrays the writer takes.

    A region in ``gpu`` (``{name: [nanoseconds per call]}``) also gets the time its calls
    kept the GPU busy, as a third array.
    """
    gpu = gpu or {}
    regions = {}
    for name, (starts, ends) in calls.items():
        if not starts:
            continue
        arrays = (np.array(starts, dtype=np.int64), np.array(ends, dtype=np.int64))
        if name in gpu:
            arrays = (*arrays, np.array(gpu[name], dtype=np.int64))
        regions[name] = arrays
    return regions


def _rank_calls(rank_jitter, ranks, solve_ms, comm_ms, gpu=False):
    """One rank's timeline, and its GPU times: ``setup``, ten ``solve`` calls and the
    ``exchange`` after each; on a GPU also the ``copy_to_device`` before the first."""
    names = ("session", "simulation", "setup", "copy_to_device", "solve", "exchange")
    calls = {name: ([], []) for name in names}
    gpu_ns = {"solve": [], "copy_to_device": []} if gpu else {}
    setup = int(4 * MS)
    clock = 2 * MS
    calls["setup"][0].append(clock)
    calls["setup"][1].append(clock + setup)
    clock += setup
    if gpu:
        copy = int(3 * MS)
        calls["copy_to_device"][0].append(clock)
        calls["copy_to_device"][1].append(clock + copy)
        gpu_ns["copy_to_device"].append(int(copy * 0.85))
        clock += copy
    for _ in range(10):
        work = int(solve_ms * MS * rank_jitter)
        calls["solve"][0].append(clock)
        calls["solve"][1].append(clock + work)
        if gpu:
            gpu_ns["solve"].append(int(work * 0.93))
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
    return {"scope_profiler.session": calls.pop("session"), **calls}, gpu_ns


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


def write_run(
    path: Path,
    ranks: int,
    *,
    solve_ms: float,
    comm_ms: float,
    seed: int,
    extras=False,
    threads: int = 1,
    gpu: bool = False,
    chip: str = "synthetic CPU",
):
    """Write one run of ``ranks`` MPI ranks of ``threads`` OpenMP threads each, on a GPU or not."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    metadata = {
        "mpi_size": ranks,
        "omp_num_threads": threads,
        "num_nodes": max(1, math.ceil(ranks * threads / 4)),
        "total_cores": ranks * threads,
        "timestamp": "2026-10-17T12:00:00Z",
        "scope_profiler_version": "sample",
        "platform": "synthetic",
        "chip_information": chip,
    }
    with ProfilingWriter(path, metadata) as writer:
        for rank in range(ranks):
            jitter = 1.0 + 0.04 * rng.standard_normal()
            payload = {}
            if extras and rank == 0:
                payload = _extras(int(solve_ms * MS * 10 * jitter))
            calls, gpu_ns = _rank_calls(jitter, ranks, solve_ms, comm_ms, gpu)
            writer.write_rank(
                rank,
                RankPayload(
                    regions=_spans(calls, gpu_ns),
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
    # Hybrid scaling: ranks and threads grow together, so the scaling charts can be drawn over
    # MPI ranks, nodes, OpenMP threads or their product.
    for ranks, threads in ((1, 1), (2, 1), (2, 2), (4, 2), (4, 4), (8, 4)):
        write_run(
            DATA / "poisson-hybrid" / f"{ranks}r-{threads}t.h5",
            ranks,
            threads=threads,
            solve_ms=80.0 / (ranks * threads**0.8),
            comm_ms=0.5 * math.log2(ranks) if ranks > 1 else 0.0,
            seed=300 + 10 * ranks + threads,
        )
    # The same problem on a CPU node and on a GPU node; the GPU run records how long the GPU was
    # busy in each call, and what it spends on moving data to it.
    folder = DATA / "vlasov-cpu-gpu"
    write_run(
        folder / "cpu-node.h5",
        8,
        threads=2,
        solve_ms=34.0,
        comm_ms=1.4,
        seed=400,
        chip="synthetic 2x64-core CPU node",
    )
    write_run(
        folder / "gpu-node.h5",
        4,
        solve_ms=7.0,
        comm_ms=0.6,
        seed=401,
        gpu=True,
        chip="synthetic 4-GPU node",
    )
    for name, color, peak in (("cpu-node", "#1f77b4", 0.8), ("gpu-node", "#d62728", 0.55)):
        (folder / f"{name}-density.svg").write_text(_density_figure(name, color, peak))
    (folder / "run.py").write_text(RUN_SCRIPT)
    (folder / "cpu-node.yml").write_text(
        PARAMETERS.format(device="cpu", ranks=8, threads=2)
    )
    (folder / "gpu-node.yml").write_text(
        PARAMETERS.format(device="gpu", ranks=4, threads=1)
    )
    # A nightly job: the same strong-scaling study on five evenings, the last of them slower.
    # Each evening's directory has a meta.yml with its date and commit.
    commits = ("a1b2c3d", "b2c3d4e", "c3d4e5f", "d4e5f6a", "e5f6a7b")
    for night, (day, drift) in enumerate(
        (("2026-10-13", 1.00), ("2026-10-14", 1.01), ("2026-10-15", 0.99), ("2026-10-16", 1.00), ("2026-10-17", 1.18))
    ):
        for ranks in (1, 2, 4):
            (DATA / "poisson-nightly" / day / "meta.yml").write_text(
                f"date: {day}\ninfo:\n  commit: {commits[night]}\n"
            )
            write_run(
                DATA / "poisson-nightly" / day / f"np{ranks}.h5",
                ranks,
                solve_ms=40.0 / ranks * drift,
                comm_ms=0.5 * math.log2(ranks),
                seed=500 + 10 * night + ranks,
            )
    write_run(
        DATA / "turbulence" / "np1.h5",
        1,
        solve_ms=90.0,
        comm_ms=0.0,
        seed=200,
        extras=True,
    )
    print(f"Wrote {len(list(DATA.rglob('*.h5')))} sample files to {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
