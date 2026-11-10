# Benchmarks

This document separates what the current code measures from what later work will measure. Targets are acceptance criteria, not results. Results are written to [results.md](results.md) and [uplift-case-study.md](uplift-case-study.md), including negative findings.

## 1. Claims by phase

Phase 1 is implemented and makes three claims:

1. The experiment readout is statistically calibrated.
2. Every reported estimate has an interval, and the interval label matches the configured alpha.
3. The simulation benchmark is reproducible from a fixed seed.

Phase 2 is now partially implemented and measured on the Hillstrom holdout. The measured claims are narrow:

- A T-learner can be fitted, scored, and evaluated without touching the holdout until the final report.
- The ranking has a measured Qini and AUUC on holdout. On Hillstrom the Qini is near zero, so the claim that the model ranks persuadable customers well is **not supported**.
- A fixed-fraction policy has a measured holdout profit and a bootstrap interval. The interval conditions on the selected customers and excludes model-selection uncertainty.

Phase 2 claims still not measured:

- A propensity baseline or a like-for-like comparison against it.
- Policy value under IPS or DR estimation.
- Policy regret against a known best policy.
- Ranking stability across seeds or bootstrap resamples.

Phase 3 is partially implemented and measured on Hillstrom:

- A dollar budget converts to the expected number of contacts through the stated cost per contact.
- The same holdout ranking is re-priced across a budget range, and the selected rows can be exported in rank order.

Phase 3 claims still not measured:

- Value/cost sensitivity, break-even value, and a risk-adjusted lower-bound policy.
- The pipeline holds at Criteo scale.
- Policy value under IPS or DR estimation.

A Qini curve alone does not prove any of these. The negative Hillstrom result stays in the report.

## 2. Protocol

- **Seed:** 42 for the simulation and the Hillstrom bootstrap.
- **Simulation size:** 10,000 rows per replication, 50/50 allocation except the unbalanced scenario.
- **Simulation replications:** 5,000 for the headline run; 200 for a fast check.
- **Alpha:** 0.05.
- **Hillstrom readout:** full 64,000 rows, 2,000 stratified bootstrap draws.
- **Primary outcome:** `visit` for Hillstrom; `visit` for Criteo when that phase lands.
- **Outputs:** `results/bench.json`, `docs/results.md`, `results/uplift.json`, `reports/uplift.md`, and `results/targets.csv`.
- **Commands:** `uv run upliftlab simulate --scenario all --replications 5000 --out results/bench.json --markdown docs/results.md --force`, `uv run upliftlab uplift hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/uplift.json --markdown reports/uplift.md --force`, and `uv run upliftlab target hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/targets.csv --force`.

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

## 4. Phase 2 and Phase 3 acceptance criteria

| Check | Target | Measurement | Status |
| --- | --- | --- | --- |
| Qini / AUUC | Positive and meaningfully above random | Hillstrom holdout | **Fail on strength**: Qini 0.004, effectively random |
| Policy value | Beat random at the same budget | Hillstrom holdout, 20% budget | Point estimate passes: $142.55 vs $80.48; no test of the difference |
| Calibration | Observed uplift rises with predicted uplift | Hillstrom holdout quintiles | **Fail**: observed curve is non-monotone |
| Dollar-budget mapping | $128 at $0.05 converts to 2,560 contacts | Hillstrom holdout | Pass |
| Profit curve | 20 points spanning 5% to 100% | Hillstrom holdout | Pass: descriptive, profit non-monotone |
| Propensity baseline | Include in the same table | Holdout | Not implemented |
| Policy regret | Low relative to the known best policy | Heterogeneous-effect simulation | Not run: simulator lacks potential outcomes |
| Delta-method coverage | 95% plus or minus 2 MCSE | Ratio-metric simulation | Not run: ratio metrics not implemented |

The Phase 2 rows above are the honest result, not a success story. The model pipeline runs and is evaluated correctly, but Hillstrom does not give a strong ranking signal with this T-learner.

## 5. Phase 1 simulation matrix

| Scenario | Treatment effect | Allocation | What it measures |
| --- | --- | --- | --- |
| Null | Zero everywhere | 50/50 | Type I error and coverage |
| Constant | +3 percentage points | 50/50 | Power and coverage |
| Heterogeneous | +4 points per unit of score, average +2 | 50/50 | ATE calibration under effect heterogeneity |
| Harmful | -2 percentage points | 50/50 | Sign handling and power |
| Unbalanced | +2 percentage points | 20/80 | Precision loss under unequal allocation |

The heterogeneous scenario measures the average effect only. The simulator does not produce potential outcomes, so it does not measure Qini, decile calibration, or regret. Phase 2 measures Qini, calibration, and policy value on the real Hillstrom holdout instead.

## 6. Hillstrom readout

- 64,000 customers, three randomized arms.
- Primary contrast: any e-mail versus no e-mail.
- Primary outcome: `visit`. Secondary: `conversion`, `spend`.
- CUPED covariate: `history` (past 12-month spend).
- Phase 1 result: ATE +0.0609 (95% CI 0.0554 to 0.0663), SRM p = 0.9037.
- CUPED: theta 0.0001, correlation 0.065, variance reduction 0.4%.

The 0.4% variance reduction is a real miss, not a rounding issue. With in-sample theta, variance reduction is the squared correlation; reaching 20% would require `|r| >= 0.45` between `history` and `visit`. The target was pre-specified in this document, not in an external registry, and it is not changed after seeing the result. A future Criteo or pre-period-rich dataset should carry a justified target instead.

The Mens-versus-Womens contrast is **not** in the Phase 1 report. It is a planned secondary analysis, because the headline estimand is assignment to a 50/50 mixture of the two e-mails.

### Uplift and policy result (Phase 2)

The Phase 2 command is

```powershell
uv run upliftlab uplift hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/uplift.json --markdown reports/uplift.md --force
```

The model is a T-learner with two `HistGradientBoostingClassifier` models. The split is 38,400 train, 12,800 validation, 12,800 holdout, stratified by treatment and outcome. The selected candidate used 15 leaves and learning rate 0.06; selection maximized validation AUUC gain. The holdout was scored once.

| Quantity | Value |
| --- | ---: |
| Holdout ATE | +0.0610 (95% CI 0.0489 to 0.0732) |
| Qini coefficient | 0.004 |
| AUUC | 0.0204 |
| Top-decile uplift | 0.0722 |

| Policy | Budget | Customers | Incremental visits | Value | Cost | Profit | ROI | 95% bootstrap CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uplift model | 20% | 2,560 | 135.3 | $270.55 | $128.00 | $142.55 | 111.4% | [$37.25, $238.31] |
| Treat all | 100% | 12,800 | 521.2 | $1,042.39 | $640.00 | $402.39 | 62.9% | n/a |
| Random | 20% | 2,560 | 104.2 | $208.48 | $128.00 | $80.48 | 62.9% | n/a |

Predicted uplift rises across the five holdout rank buckets, but observed uplift does not: Q1 0.0682, Q2 0.0706, Q3 0.0455, Q4 0.0421, Q5 0.0805. That is evidence against a strong ranking, and it is consistent with the near-zero Qini.

The model policy beats random on this holdout by a point estimate, but the difference is not tested, the bootstrap excludes model-selection uncertainty, and treat-all spends five times as much. The case study in [uplift-case-study.md](uplift-case-study.md) states these limits in full.

The profit curve at the same value and cost re-prices this ranking from 5% to 100%. Profit is $63.19 at 5%, $142.55 at 20%, $142.67 at 25%, $132.02 at 30%, $160.86 at 50%, and $402.39 at 100%. ROI falls from 197.5% to 62.9% as spend grows. The middle of the curve is non-monotone, which is consistent with a weak ranking plus a positive average effect. It is not evidence that 100% is the right campaign size. The `target` export for the $128 budget writes 2,560 rows with the original dataframe index, rank, and predicted uplift.

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
- All baselines appear in the same table as the uplift model.
- Negative or null results stay in the report.
- Statistical significance and practical significance are reported separately.
- Cost and value assumptions are stated next to the profit numbers.
- Causal language is limited to what randomization supports. Criteo's `exposure` is not treated as randomized.
- The report distinguishes "the model ranks well" from "the policy makes money."

## 9. Runtime budget

These are provisional for the stages that do not exist. The measured stages are the simulation, the readout, and the Hillstrom uplift run.

| Stage | Target |
| --- | --- |
| Fast tests | Under 60 seconds |
| Phase 1 simulation, 5,000 replications | Under 5 minutes |
| Hillstrom readout | Under 2 minutes |
| Hillstrom uplift and policy | Under 5 minutes |
| Criteo 10% case study | Under 10 minutes |
| Full Phase 2/3 benchmark | Under 30 minutes |

If a run exceeds the budget, vectorize or reduce the scenario set before cutting a statistical check.

## 10. Results and reproduction

The generated table lives in [results.md](results.md). It is written by the benchmark command and is not edited by hand.

```powershell
uv sync
uv run upliftlab simulate --scenario all --replications 5000 --out results/bench.json --markdown docs/results.md --force
uv run upliftlab analyze hillstrom --out reports/hillstrom-readout.md --json results/hillstrom-readout.json
uv run upliftlab uplift hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/uplift.json --markdown reports/uplift.md --force
uv run upliftlab target hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/targets.csv --force
```

Raw data and generated results are not committed. The Criteo case study is Phase 4 work and does not exist yet.
