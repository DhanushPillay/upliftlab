# upliftlab

**From experiment readout to budget-constrained targeting.**

Most A/B tests stop at an average effect. Most uplift models stop at a ranking. Neither tells a growth team how many customers to treat, or what the campaign is worth.

`upliftlab` is a small, CPU-only Python toolkit for that decision. Phase 1 is implemented: a randomized experiment readout with sample-ratio mismatch, covariate balance, a Welch average treatment effect, a stratified bootstrap, CUPED variance reduction, and a simulation benchmark that checks calibration. The uplift and budget layers are next.

## What works now

- `fetch` downloads the Hillstrom e-mail dataset, verifies its SHA-256, and caches it under `data/raw/`.
- `analyze` checks the three-arm randomization, compares covariate balance, estimates the any-email versus no-email effect on `visit`, bootstraps the interval, and reports CUPED variance reduction using pre-period `history`.
- Output is a Markdown brief and canonical JSON with a schema version.
- Failures are typed and exit nonzero: bad config, schema, checksum, report write, or analysis.

## Quickstart

```powershell
uv sync
uv run upliftlab fetch hillstrom
uv run upliftlab analyze hillstrom --out reports/hillstrom-readout.md --json results/hillstrom-readout.json
```

The defaults match `configs/readout.toml`; pass `--config` only when you want a different outcome, covariate, alpha, bootstrap count, or seed. Run the first two commands on separate lines in PowerShell. `uv run upliftlab analyze hillstrom` without `--out` prints the brief to stdout.

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

The decision needs three things together: a trustworthy average effect, a ranking of persuadable customers, and a budget rule with uncertainty on profit. Phase 1 delivers the first and a calibration check. Phase 2 adds the ranking. Phase 3 adds the budget decision.

## Design choices

- **Intervals before headlines.** Every estimate has a confidence interval. Point estimates alone are incomplete.
- **Baselines are mandatory.** Uplift models will be compared with treat-all, random targeting, and a propensity baseline. If a model cannot beat treat-all on holdout, the report will say so.
- **Calibration is checked.** Ranking well and predicting uplift are different. The later report will compare predicted and observed uplift by decile.
- **Simulation before claims.** Type I error and interval coverage are measured on synthetic data with known truth. Policy regret will be measured when the targeting layer exists.
- **Small surface.** Python, NumPy, pandas, SciPy. No distributed stack for a 14M-row dataset that fits in memory.
- **No fake production layer.** This is a batch CLI and library. There is no dashboard, container, or model registry.

## Case studies

| Dataset | Scale | Role |
| --- | --- | --- |
| Hillstrom e-mail | 64,000 customers, 3 randomized arms | Current readout case study |
| Criteo Uplift v2.1 | 13.98M rows, deterministic 10% sample for routine runs | Planned scale test |

## Status

Phase 0 and Phase 1 are implemented.

- [x] Repository, docs, packaging, typed results, tests
- [x] Hillstrom fetch and schema validation
- [x] SRM, balance, Welch ATE, stratified bootstrap, CUPED
- [x] Simulation calibration: Type I error, coverage, power, MCSE
- [x] Markdown and JSON readout
- [ ] Phase 2: sequential and Bayesian readout, uplift models, Qini/AUUC, policy value
- [ ] Phase 3: budget targeting, Criteo, full report
- [ ] First green CI run on `main` (workflow and security policy are committed; not yet executed)
- [ ] Release workflow (PyPI publish)

## Benchmark result

The Phase 1 simulation benchmark ran 5,000 replications per scenario at n = 10,000, seed 42:

- Null Type I error: 5.24% +/- 0.31% at alpha 0.05.
- Coverage: 94.3% to 95.1% across scenarios, all within two MCSE of 95%.
- Power: 99.6% for a constant +3 point effect, 89.0% for a heterogeneous +2 point average, 70.0% under 20/80 allocation.

These are calibration results for the readout only. Qini, policy value, and regret are not measured until Phase 2/3. The full table and run metadata are in [docs/results.md](docs/results.md). The Hillstrom smoke readout is in the same protocol; its CUPED variance reduction is 0.4% because `history` correlates only 0.065 with `visit`, so the 20% target is reported as missed rather than hidden.

Quality gates: `pytest` with an 85% coverage floor, `ruff check`, `ruff format --check`, and `mypy --strict`.

## Project layout

```text
src/upliftlab/
  cli.py           # argparse and formatting; no statistics
  config.py        # frozen readout config, TOML loading
  datasets/        # registry, checksum download, Hillstrom loader
  experiment/      # SRM, balance, Welch ATE, bootstrap, CUPED
  simulation/      # synthetic scenarios, calibration runner, Markdown table
  report/          # Markdown readout
  results.py       # typed results and canonical JSON
tests/
docs/
configs/
```

## Documentation

- [Methodology](docs/methodology.md): estimands, estimators, metrics, policy rule, assumptions.
- [Benchmarks](docs/benchmarks.md): protocol, acceptance criteria, scenarios, reporting rules.
- [Data](docs/data.md): sources, checksums, licenses, preprocessing.
- [Results](docs/results.md): generated simulation benchmark with run metadata.

## Data and licenses

No raw data is committed. Datasets are downloaded on demand and verified against pinned checksums.

- Hillstrom e-mail: 64,000 customers, published by Kevin Hillstrom (MineThatData). No formal open license is stated at the source; cite it and do not redistribute the raw file.
- Criteo Uplift v2.1: 13,979,592 rows, CC BY-NC-SA 4.0 (non-commercial). Not part of Phase 1.

See [docs/data.md](docs/data.md) for URLs, checksums, and terms. Code is MIT licensed; the Criteo data is not covered by that license. Criteo-derived outputs (tables, plots, models) inherit CC BY-NC-SA 4.0: keep them non-commercial and share-alike, and do not publish row-level Criteo predictions or trained models.

## Acknowledgements

- Kevin Hillstrom for the MineThatData e-mail dataset.
- Criteo Research for Uplift v2.1 (Diemert, Betlei, Renaudin, Amini, 2018).
- Deng, Xu, Kohavi, Walker (2013) for CUPED.
- Radcliffe (2007) for the Qini curve; Devriendt, Guns, Verbeke (2020) for uplift evaluation.
- The scikit-uplift project for reference implementations and dataset conventions.
