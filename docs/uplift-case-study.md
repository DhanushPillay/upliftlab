# Hillstrom uplift and policy case study

This is a real run on the Hillstrom e-mail experiment, not a synthetic result. It answers a narrow question: if a growth team ranked customers by a T-learner's predicted uplift and contacted the top 20%, what would that policy have been worth on held-out customers?

The answer is positive against random targeting, but the ranking signal is weak. Both facts belong in the report.

## Command

```powershell
uv run upliftlab uplift hillstrom --outcome visit --budget 0.2 --out results/uplift.json --markdown reports/uplift.md
```

Assumptions: each incremental `visit` is worth $2.00, each contact costs $0.05, and the budget covers 20% of the holdout. The model is a T-learner with two histogram gradient-boosted classifiers. The split is 60% train, 20% validation, 20% holdout, stratified by treatment and outcome. The holdout is touched once, after model selection.

## Result

| Item | Value |
| --- | ---: |
| Rows | 64,000 |
| Split | 38,400 train / 12,800 validation / 12,800 holdout |
| Selected candidate | 15 leaves, learning rate 0.06 |
| Holdout ATE | +0.0610 (95% CI 0.0489 to 0.0732) |
| Qini coefficient | 0.004 |
| AUUC | 0.0204 |
| Top-decile uplift | 0.0722 |

| Policy | Budget | Customers | Incremental visits | Value | Cost | Profit | ROI | 95% bootstrap CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uplift model | 20% | 2,560 | 135.3 | $270.55 | $128.00 | $142.55 | 111.4% | [$37.25, $238.31] |
| Treat all | 100% | 12,800 | 521.2 | $1,042.39 | $640.00 | $402.39 | 62.9% | n/a |
| Random | 20% | 2,560 | 104.2 | $208.48 | $128.00 | $80.48 | 62.9% | n/a |

The model policy earns more profit than random targeting at the same budget. Treat-all earns more total profit, but it also spends five times as much. The fair comparison for a fixed budget is the random row; treat-all answers a different question.

## Calibration

| Segment | Customers | Treated share | Predicted uplift | Observed uplift | 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q1 (lowest) | 2,560 | 66% | 0.0005 | 0.0682 | [0.0406, 0.0958] |
| Q2 | 2,560 | 67% | 0.0373 | 0.0706 | [0.0461, 0.0950] |
| Q3 | 2,560 | 67% | 0.0580 | 0.0455 | [0.0199, 0.0711] |
| Q4 | 2,560 | 68% | 0.0808 | 0.0421 | [0.0136, 0.0707] |
| Q5 (highest) | 2,560 | 66% | 0.1286 | 0.0805 | [0.0511, 0.1100] |

The predicted ranking rises from Q1 to Q5. The observed ranking does not: Q2 is slightly above Q1, then Q3 and Q4 are lower, and Q5 is the highest. This is a weak calibration result. The model does not cleanly separate persuadable customers on this holdout.

The Qini coefficient of 0.004 says the same thing in one number. It is barely above a random ranking.

## What this does and does not show

It shows that the full path works: load and verify the dataset, split it without leakage, fit a model, select a candidate on validation AUUC, evaluate once on holdout, price a fixed-budget policy, and report uncertainty.

It does not show that the model will find persuadable customers in a new campaign. The policy gain over random is a point estimate from one holdout, not a tested difference between policies. The bootstrap interval resamples outcomes within arm and conditions on the customers the model selected; it does not include model-selection uncertainty. The observed segment curve is non-monotone, which is evidence against a strong ranking claim, not a rounding issue.

Hillstrom's treatment is assignment to any e-mail, so the estimate is intention-to-treat. Criteo, propensity baselines, IPS/DR, policy regret, and multi-budget optimization are not part of this case study.

## Reproduction

Outputs are generated, not hand-edited:

- `results/uplift.json`: canonical JSON with schema version 2.
- `reports/uplift.md`: Markdown report.

The full test suite covers the Qini arithmetic, policy pricing, configuration validation, fit/report path, API routes, and report rendering. The real-data run is a case study, not a unit test.
