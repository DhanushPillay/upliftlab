# Contributing

## Setup

```bash
uv sync
uv run pre-commit install
```

`uv` creates the virtual environment and installs the locked dependencies. Python 3.12 is required.

## Checks before a pull request

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=upliftlab --cov-report=term-missing
```

The coverage floor is 85%. New statistical code needs a hand-computed or brute-force test, not only a shape assertion. New CLI behavior needs an integration test through `main()`.

## Scope

- Keep the library free of printing and argument parsing; that belongs in `cli.py`.
- No raw data, model binaries, or generated reports in Git.
- No new dependency without a stated need and a lockfile update.
- No `utils.py`, `helpers.py`, `core.py`, or `common.py`. Name the domain.
- Do not add Docker, a dashboard, or a service layer for this batch CLI.
- A bug fix includes the regression test that failed before the fix.

## Commits

Small, imperative commits are preferred. Do not commit `data/`, `results/`, `reports/`, `.venv/`, or caches. Open a pull request for changes that alter an estimator, a metric, or a report contract.
