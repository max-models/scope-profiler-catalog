#!/usr/bin/env bash
# Put the profiling files that catalogue.yaml lists into data/.
#
# The workflow runs this before `scope-profiler site`. The template ships synthetic sample
# files so that a fresh copy builds; a fork replaces the body with its own source, for example
#
#   git clone --depth 1 https://github.com/my-org/profiling-data data
#   gh release download --repo my-org/my-code --pattern '*.h5' --dir data
#   aws s3 sync s3://my-bucket/profiling data --exclude '*' --include '*.h5'
#
# and removes scripts/make_sample_data.py.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python scripts/make_sample_data.py
