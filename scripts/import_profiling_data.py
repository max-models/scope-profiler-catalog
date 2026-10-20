"""Write a catalogue manifest for a checkout of struphy's ``profiling-data`` repository.

Each directory of that repository is one execution of a test case: ``case_metadata.json`` names
the case, its commit and its runs, and every run's folder holds a ``runNN.h5`` profile, plots as
PNG files and the ``parameters.py`` the job used. Directories of the same case become the
executions of one catalogue case, so a case that is run again and again keeps one page:

    git clone git@github.com:struphy-hub/profiling-data
    python scripts/import_profiling_data.py profiling-data -o catalogue.profiling-data.yaml \\
        --case poisson_cube_strong_scaling --last 4 --images 'phi_slices_xy.png,rhs_3d.png'
    uv run scope-profiler site catalogue.profiling-data.yaml -o docs

The result is a local manifest (git-ignored): the profiling data is large and stays out of this
repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

STRUPHY = "https://github.com/struphy-hub/struphy"


def _words(name: str) -> str:
    """``VlasovAmpereOneSpecies`` as ``Vlasov Ampere One Species``."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def _scaling(identifier: str) -> str:
    """Which scaling chart a case wants, from the name its authors gave it."""
    if "weak" in identifier:
        return "weak"
    if "_vs_" in identifier:
        return "none"
    return "strong"


def _execution(
    directory: Path, meta: dict, manifest_dir: Path, images: list[str]
) -> dict:
    general = meta["general_information"]
    software = meta["software_information"]
    commit = software["struphy_commit"][:8]
    parameters = directory / "parameters.py"
    runs = []
    for entry in sorted(meta["runs"], key=lambda run: run["launch_id"]):
        folder = directory / entry["folder"]
        profile = folder / f"{Path(entry['folder']).name.replace('results-', '')}.h5"
        if not profile.is_file():
            continue
        run = {"path": os.path.relpath(profile, manifest_dir)}
        if parameters.is_file():
            run["files"] = [os.path.relpath(parameters, manifest_dir)]
        found = [
            os.path.relpath(path, manifest_dir)
            for pattern in images
            for path in sorted(folder.glob(pattern))
        ]
        if found:
            run["images"] = found
        runs.append(run)
    stamp = general["time_date_utc"]
    return {
        "id": f"{general['datetime_token']}-{commit}",
        "label": f"{stamp[:10]} {stamp[11:16]}",
        "date": stamp,
        "info": {
            "commit": commit,
            "cluster": meta["hardware_information"].get("cluster_name"),
            "language": software.get("pyccel_language"),
        },
        "runs": runs,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", type=Path, help="the profiling-data checkout")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("catalogue.profiling-data.yaml")
    )
    parser.add_argument(
        "--case", action="append", help="a test case identifier (default: all)"
    )
    parser.add_argument(
        "--last", type=int, default=None, help="only the newest N executions of a case"
    )
    parser.add_argument(
        "--images",
        default="*.png",
        help="comma-separated globs of the images to show on a run's page (default: all PNGs)",
    )
    parser.add_argument("--base", default="/scope-profiler-catalog")
    args = parser.parse_args(argv)

    manifest_dir = args.output.resolve().parent
    images = [pattern for pattern in args.images.split(",") if pattern]
    cases: dict[str, list[tuple[Path, dict]]] = {}
    for path in sorted(args.root.glob("*/case_metadata.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        identifier = meta["general_information"]["test_case_identifier"]
        if args.case and identifier not in args.case:
            continue
        cases.setdefault(identifier, []).append((path.parent.resolve(), meta))
    if not cases:
        print(f"no case found in {args.root}", file=sys.stderr)
        return 1

    entries = []
    for identifier, found in cases.items():
        executions = [
            _execution(directory, meta, manifest_dir, images)
            for directory, meta in found
        ]
        executions = [item for item in executions if item["runs"]]
        if args.last:
            executions = executions[-args.last :]
        if not executions:
            continue
        latest = found[-1][1]
        general = latest["general_information"]
        software = latest["software_information"]
        entry = {
            "id": identifier,
            "title": general["test_case_name"],
            "description": general["test_case_description"],
            "group": _words(general.get("struphy_model_used") or "Struphy"),
            "tags": [
                tag
                for tag in (
                    latest["hardware_information"].get("cluster_name"),
                    software.get("pyccel_language"),
                )
                if tag
            ],
            "scaling": _scaling(identifier),
            "code": [
                {
                    "url": f"{STRUPHY}/tree/{software['struphy_commit']}",
                    "label": f"struphy @ {software['struphy_commit'][:8]}",
                }
            ],
        }
        if len(executions) == 1:
            entry["info"] = executions[0]["info"]
            entry["runs"] = executions[0]["runs"]
        else:
            entry["executions"] = executions
        entries.append(entry)

    document = {
        "title": "Struphy profiling data",
        "description": "Profiling runs of the Struphy test cases.",
        "base": args.base,
        "cases": entries,
    }
    args.output.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    runs = sum(
        len(item["runs"])
        for entry in entries
        for item in entry.get("executions", [entry])
    )
    print(f"Wrote {len(entries)} cases ({runs} runs) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
