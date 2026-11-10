# upliftlab

**From experiment readout to budget-constrained targeting.**

Most A/B tests stop at an average effect. Most uplift models stop at a ranking. Neither tells a growth team how many customers to treat, or what the campaign is worth.

`upliftlab` is a small, CPU-only toolkit for that decision. It is implemented end to end: a randomized experiment readout with sample-ratio mismatch, covariate balance, a Welch average treatment effect, a stratified bootstrap, CUPED variance reduction, and a simulation benchmark; a T-learner uplift model with Qini/AUUC ranking; a fixed-budget targeting policy with bootstrap uncertainty; and a FastAPI + React interface that runs locally in Docker.

## What works now

- `fetch` downloads the Hillstrom e-mail dataset, verifies its SHA-256, and caches it under `data/raw/`.
- `analyze` checks the three-arm randomization, compares covariate balance, estimates the any-email versus no-email effect on `visit`, bootstraps the interval, and reports CUPED variance reduction using pre-period `history`.
- `uplift` fits a T-learner, scores holdout customers by predicted uplift, reports Qini/AUUC, compares predicted and observed uplift by rank bucket, and prices a fixed-budget policy against treat-all and random targeting.
- A FastAPI service exposes the readout and policy; a React interface renders them with the budget controls.
- `docker compose up --build` runs the API and built frontend as one local container.
- Output is Markdown, canonical JSON with a schema version, and a JSON API.
- Failures are typed and exit nonzero: bad config, schema, checksum, report write, or analysis.

## Quickstart

```powershell
uv sync
uv run upliftlab fetch hillstrom
uv run upliftlab analyze hillstrom --out reports/hillstrom-readout.md --json results/hillstrom-readout.json
uv run upliftlab uplift hillstrom --budget 0.2 --out results/uplift.json --markdown reports/uplift.md
```

The readout defaults match `configs/readout.toml`; pass `--config` only when you want a different outcome, covariate, alpha, bootstrap count, or seed. The uplift command auto-downloads the dataset when the cache is empty. Run the commands on separate lines in PowerShell. Without `--out` or `--markdown`, both commands print to stdout.

### Local UI

```powershell
docker compose up --build
```

Open <http://localhost:8000>. The container serves the API and the built React app, and keeps the downloaded dataset in the `upliftlab-data` volume. `GET /api/health` is the health check; `GET /docs` is the generated API documentation.

For frontend development, run `uv run uvicorn upliftlab.api.main:app --reload` and `npm run dev` in `web/`. Vite proxies `/api` to the API on port 8000.

## What the readout contains

| Section | Question it answers |
| --- | --- |
| Sample ratio | Did the arms receive the intended share of traffic? |
| Balance | Are treated and control comparable before the outcome? |
| Average effect | How much did the email change visit rate, with what interval? |
| Bootstrap | Does a resampling interval agree with the Welch interval? |
| CUPED | How much variance does the pre-period covariate remove? |
| Caveats | What this readout does not establish |

CUPED is computed in-sample for the readout. A targeting model must fit theta and all preprocessing on training data only; the report says so explicitly.

## Why this exists

Average lift is not a targeting rule. A campaign can lift revenue on average while most of the spend goes to customers who would have bought anyway. A response model makes this worse: it ranks sure things highest. A Qini curve ranks uplift models but does not say where to stop spending.

The decision needs three things together: a trustworthy average effect, a ranking of persuadable customers, and a budget rule with uncertainty on profit. Phase 1 delivers the first and a calibration check. Phase 2 delivers the ranking and a fixed-budget policy. Phase 3 covers the Criteo scale case and release work.

## Design choices

- **Intervals before headlines.** Every estimate has a confidence interval. Point estimates alone are incomplete.
- **Baselines are mandatory.** The policy is compared with treat-all and random targeting at the same budget. A propensity baseline and off-policy evaluation are not implemented yet, so the comparison is weaker than it should be.
- **Calibration is checked, not assumed.** The report compares predicted and observed uplift across five rank buckets. The Hillstrom holdout is visibly non-monotone, and the report says so instead of hiding it.
- **Simulation before claims.** Type I error and interval coverage are measured on synthetic data with known truth. Policy regret is not measured yet.
- **Small surface.** Python, NumPy, pandas, SciPy, scikit-learn, and FastAPI. No distributed stack for a dataset that fits in memory. The React app compiles to static files.
- **Real but minimal deployment.** One container serves the API and the built UI. There is no database, queue, model registry, or auth layer, because the app only reads a public dataset and refits a cached model. The container runs as a non-root user and binds locally.

## Case studies

| Dataset | Scale | Role |
| --- | --- | --- |
| Hillstrom e-mail | 64,000 customers, 3 randomized arms | Readout, uplift ranking, and policy case study |
| Criteo Uplift v2.1 | 13.98M rows, deterministic 10% sample for routine runs | Planned Phase 3 scale test |

## Status

Phases 0, 1, and the implemented part of Phase 2 are done.

- [x] Repository, docs, packaging, typed results, tests
- [x] Hillstrom fetch and schema validation
- [x] SRM, balance, Welch ATE, stratified bootstrap, CUPED
- [x] Simulation calibration: Type I error, coverage, power, MCSE
- [x] Markdown and JSON readout
- [x] Phase 2: T-learner uplift model, Qini/AUUC, rank-bucket calibration, fixed-budget policy
- [x] FastAPI service, React interface, Docker Compose
- [x] First green CI run on `main`
- [ ] Phase 2 remaining: sequential and Bayesian readout, ratio metrics, MDE, guardrails, multiple testing, propensity baseline, IPS/DR, policy regret
- [ ] Phase 3: Criteo loader and case study, full report
- [ ] Release workflow (PyPI publish)

## Benchmark result

The Phase 1 simulation benchmark ran 5,000 replications per scenario at n = 10,000, seed 42:

- Null Type I error: 5.24% +/- 0.31% at alpha 0.05.
- Coverage: 94.3% to 95.1% across scenarios, all within two MCSE of 95%.
- Power: 99.6% for a constant +3 point effect, 89.0% for a heterogeneous +2 point average, 70.0% under 20/80 allocation.

These are calibration results for the readout only. Qini, policy value, and policy regret are reported separately below or not yet measured. The full table and run metadata are in [docs/results.md](docs/results.md). The Hillstrom readout is in the same protocol; its CUPED variance reduction is 0.4% because `history` correlates only 0.065 with `visit`, so the 20% target is reported as missed rather than hidden.

## Uplift and policy result

The uplift command fits a T-learner on the Hillstrom data, selects a candidate on validation AUUC, and evaluates once on a 12,800-customer holdout:

- Holdout ATE: +0.0610 (95% CI 0.0489 to 0.0732).
- Qini coefficient: 0.004, or close to random ranking.
- Top-decile uplift: 0.0722, against an overall holdout uplift near 0.061.
- Policy at a 20% budget: 2,560 customers, 135.3 incremental visits, $142.55 profit, 95% bootstrap CI [$37.25, $238.31].
- Random targeting at the same budget: $80.48 profit.
- Treat-all: $402.39 profit, but it spends five times as much.

The model policy beats random on this holdout, but the ranking signal is weak: Qini is near zero and the observed uplift by predicted rank is not monotone. The bootstrap interval also conditions on the selected customers and excludes model-selection uncertainty. The honest reading is that the pipeline works and the policy comparison is positive, not that the model reliably finds persuadable customers. Full output and interpretation: [docs/uplift-case-study.md](docs/uplift-case-study.md).

Quality gates: `pytest` with an 85% coverage floor, `ruff check`, `ruff format --check`, and `mypy --strict`.

## Project layout

```text
src/upliftlab/
  cli.py           # argparse and formatting; no statistics
  config.py        # frozen readout config, TOML loading
  datasets/        # registry, checksum download, Hillstrom loader
  experiment/      # SRM, balance, Welch ATE, bootstrap, CUPED
  uplift/          # T-learner, Qini/AUUC, policy value, Markdown report
  simulation/      # synthetic scenarios, calibration runner, Markdown table
  api/             # FastAPI schemas, cached service, routes
  report/          # Markdown readout
  results.py       # typed results and canonical JSON
web/               # React + Vite interface
tests/
docs/
configs/
Dockerfile
compose.yaml
```

## Documentation

- [Methodology](docs/methodology.md): estimands, estimators, metrics, policy rule, assumptions.
- [Benchmarks](docs/benchmarks.md): protocol, acceptance criteria, scenarios, reporting rules.
- [Data](docs/data.md): sources, checksums, licenses, preprocessing.
- [Results](docs/results.md): generated simulation benchmark with run metadata.
- [Uplift case study](docs/uplift-case-study.md): actual Hillstrom uplift and policy output, including the weak ranking result.

## Data and licenses

No raw data is committed. Datasets are downloaded on demand and verified against pinned checksums.

- Hillstrom e-mail: 64,000 customers, published by Kevin Hillstrom (MineThatData). No formal open license is stated at the source; cite it and do not redistribute the raw file.
- Criteo Uplift v2.1: 13,979,592 rows, CC BY-NC-SA 4.0 (non-commercial). Planned Phase 3 scale case; not used by the current commands.

See [docs/data.md](docs/data.md) for URLs, checksums, and terms. Code is MIT licensed; the Criteo data is not covered by that license. Criteo-derived outputs (tables, plots, models) inherit CC BY-NC-SA 4.0: keep them non-commercial and share-alike, and do not publish row-level Criteo predictions or trained models.

## Acknowledgements

- Kevin Hillstrom for the MineThatData e-mail dataset.
- Criteo Research for Uplift v2.1 (Diemert, Betlei, Renaudin, Amini, 2018).
- Deng, Xu, Kohavi, Walker (2013) for CUPED.
- Radcliffe (2007) for the Qini curve; Devriendt, Guns, Verbeke (2020) for uplift evaluation.
- The scikit-uplift project for reference implementations and dataset conventions.
