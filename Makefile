# Development environment (uv) and the catalogue site (docs/, Astro + Starlight).
DOCS_PYTHON = $(shell uv run python -c "import sys; print(sys.executable)")

.PHONY: help install data catalogue check lint docs-install docs-dev docs-build docs-preview docs-clean

help:  ## list the targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install:  ## uv sync with the dev extra, the npm packages and the pre-commit hooks
	uv sync --extra dev
	cd docs && npm ci
	uv run pre-commit install

data:  ## fetch the profiling files into data/ (scripts/fetch_data.sh)
	bash scripts/fetch_data.sh

check:  ## validate catalogue.yaml and the files it lists
	uv run scope-profiler site catalogue.yaml --check

catalogue: data  ## write the catalogue pages and chart data into docs/
	uv run scope-profiler site catalogue.yaml -o docs

lint:  ## ruff
	uv run ruff check .
	uv run ruff format --check .

docs-install:  ## the npm packages of the site
	cd docs && npm ci

docs-dev: catalogue  ## live preview at http://localhost:4321/scope-profiler-catalog/
	cd docs && DOCS_VALIDATE_LINKS=false npm run dev

docs-build: catalogue  ## the static site in docs/dist, as in CI
	cd docs && npm run check:mdx && npm run build

docs-preview:  ## serve docs/dist
	cd docs && npm run preview

docs-clean:  ## remove the generated pages, chart data and build output
	rm -rf docs/src/content/docs/catalogue docs/public/catalogue docs/dist docs/.astro
