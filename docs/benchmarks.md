# Benchmarks

This document separates what Phase 1 measures from what later phases will measure. Targets are acceptance criteria, not results. Results are written to [results.md](results.md) by the benchmark command, including negative findings.

## 1. Claims by phase

Phase 1 is implemented and makes three claims:

1. The experiment readout is statistically calibrated.
2. Every reported estimate has an interval, and the interval label matches the configured alpha.
3. The simulation benchmark is reproducible from a fixed seed.

Phase 2 and Phase 3 make further claims that are **not measured yet**:

- An uplift model beats treat-all, random, and propensity baselines on holdout.
- Qini/AUUC ranking quality translates into policy value.
- A budget policy produces a useful profit estimate with honest uncertainty.
- Policy regret is low against a known best policy.

A Qini curve alone does not prove any of these. They stay out of the Phase 1 results table until the code exists.

## 2. Protocol

- **Seed:** 42 for the simulation and the Hillstrom bootstrap.
- **Simulation size:** 10,000 rows per replication, 50/50 allocation except the unbalanced scenario.
- **Simulation replications:** 5,000 for the headline run; 200 for a fast check.
- **Alpha:** 0.05.
- **Hillstrom readout:** full 64,000 rows, 2,000 stratified bootstrap draws.
- **Primary outcome:** `visit` for Hillstrom; `visit` for Criteo when that phase lands.
- **Outputs:** `results/bench.json` and a generated `docs/results.md`.
- **Command:** `uv run upliftlab simulate --scenario all --replications 5000 --out results/bench.json --markdown docs/results.md --force`.

The JSON records the seed, alpha, replication count, Python and NumPy versions, platform, and creation time. Git commit, dataset checksums, and peak memory are not recorded yet; they are required before a Criteo or policy benchmark is published. A rerun with the same seed produces the same result payload; the timestamp is run metadata and is excluded from any payload hash.

## 3. Phase 1 acceptance criteria

| Check | Target | Measurement | Status |
| --- | --- | --- | --- |
| Unit tests | All pass | `uv run pytest` | Pass |
| Type I error | 5% plus or minus 2 MCSE at alpha 0.05 | 5,000 null simulations | Pass: 5.24% +/- 0.31% |
| Interval coverage | 95% plus or minus 2 MCSE | 5,000 simulations per scenario | Pass: 94.3% to 95.1% |
| Bias | Smaller than 0.1 empirical standard errors | All Phase 1 scenarios | Pass: at most 0.0002 |
| Runtime | Under 5 minutes on the reference machine | Wall time of the full run | Measured, see results.md |
| Reproducibility | Same result payload for the same seed | Rerun and compare | Pass |

A fixed band such as 4.5% to 5.5% is not a statistical test: at 5,000 replications its edge is only about 1.6 MCSE from 5%. The report uses the +/- 2 MCSE band and always prints the MCSE.

## 4. Phase 2 and Phase 3 acceptance criteria (planned)

| Check | Target | Measurement |
| --- | --- | --- |
| Qini / AUUC | Positive, bootstrap CI excludes zero | Hillstrom and Criteo holdout |
| Policy value | Beat treat-all and propensity at some budget | Holdout profit curve |
| Calibration | Observed uplift inside the predicted decile interval for most deciles | Holdout calibration table |
| Policy regret | Low relative to the known best policy | Heterogeneous-effect simulation |
| Delta-method coverage | 95% plus or minus 2 MCSE | Ratio-metric simulation |

These rows are not run by the Phase 1 command.

## 5. Phase 1 simulation matrix

| Scenario | Treatment effect | Allocation | What it measures |
| --- | --- | --- | --- |
| Null | Zero everywhere | 50/50 | Type I error and coverage |
| Constant | +3 percentage points | 50/50 | Power and coverage |
| Heterogeneous | +4 points per unit of score, average +2 | 50/50 | ATE calibration under effect heterogeneity |
| Harmful | -2 percentage points | 50/50 | Sign handling and power |
| Unbalanced | +2 percentage points | 20/80 | Precision loss under unequal allocation |

The heterogeneous scenario measures the average effect only. It does not measure Qini, decile calibration, or regret; those require the Phase 2 uplift layer.

## 6. Hillstrom readout

- 64,000 customers, three randomized arms.
- Primary contrast: any e-mail versus no e-mail.
- Primary outcome: `visit`. Secondary: `conversion`, `spend`.
- CUPED covariate: `history` (past 12-month spend).
- Phase 1 result: ATE +0.0609 (95% CI 0.0554 to 0.0663), SRM p = 0.9037.
- CUPED: theta 0.0001, correlation 0.065, variance reduction 0.4%.

The 0.4% variance reduction is a real miss, not a rounding issue. With in-sample theta, variance reduction is the squared correlation; reaching 20% would require `|r| >= 0.45` between `history` and `visit`. The target was pre-specified in this document, not in an external registry, and it is not changed after seeing the result. A future Criteo or pre-period-rich dataset should carry a justified target instead.

The Mens-versus-Womens contrast is **not** in the Phase 1 report. It is a planned secondary analysis, because the headline estimand is assignment to a 50/50 mixture of the two e-mails.

## 7. Criteo Uplift (planned)

- 13,979,592 rows (the unbiased v2.1 release), 12 anonymized features `f0` through `f11`.
- Routine runs use a deterministic 10% sample. The sample rule hashes row ids assigned by file position, so it is order-dependent; reordering the file changes the sample.
- Primary treatment: `treatment` (randomized assignment). `exposure` is post-treatment and is not used as a covariate.
- Primary outcome: `visit`. Secondary: `conversion`.
- License: CC BY-NC-SA 4.0. Criteo-derived outputs inherit the non-commercial and share-alike terms.

No Criteo result is reported yet. The profit assumptions in `configs/benchmark.toml` are illustrative and are not used by the Phase 1 readout.

## 8. Reporting rules

- Every estimate is reported with a confidence interval.
- The primary metric is fixed before modeling and is not swapped after seeing results.
- All baselines appear in the same table as the uplift model once Phase 2 exists.
- Negative or null results stay in the report.
- Statistical significance and practical significance are reported separately.
- Cost and value assumptions are stated next to the profit numbers.
- Causal language is limited to what randomization supports. Criteo's `exposure` is not treated as randomized.
- The report distinguishes "the model ranks well" from "the policy makes money."

## 9. Runtime budget

These are provisional until the Phase 2/3 code exists.

| Stage | Target |
| --- | --- |
| Fast tests | Under 60 seconds |
| Phase 1 simulation, 5,000 replications | Under 5 minutes |
| Hillstrom readout | Under 2 minutes |
| Criteo 10% case study | Under 10 minutes |
| Full Phase 2/3 benchmark | Under 30 minutes |

If a run exceeds the budget, vectorize or reduce the scenario set before cutting a statistical check.

## 10. Results and reproduction

The generated table lives in [results.md](results.md). It is written by the benchmark command and is not edited by hand.

```powershell
uv sync
uv run upliftlab simulate --scenario all --replications 5000 --out results/bench.json --markdown docs/results.md --force
uv run upliftlab analyze hillstrom --out reports/hillstrom-readout.md --json results/hillstrom-readout.json
```

Raw data and generated results are not committed. The `uplift` and `target` commands are Phase 2 and Phase 3 work and do not exist yet.
