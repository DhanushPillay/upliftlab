# Methodology

This document records the statistical contract for `upliftlab`. It covers the estimands, estimators, evaluation metrics, budget rule, simulation design, and assumptions. The goal is to make every number in the report traceable to a definition.

Sections are labelled by phase. **Implemented** means the code exists in the current tree and is exercised by tests or a real-data run. **Planned** means the method is specified but the code does not exist yet, so no result in [results.md](results.md) or [uplift-case-study.md](uplift-case-study.md) uses it.

## 1. Scope

The project handles randomized experiments with:

- a binary treatment assignment,
- one or more outcomes (binary, continuous, or dollar-valued),
- pre-treatment covariates,
- a decision about who should receive the treatment under a budget.

The main estimand is the intent-to-treat (ITT) effect. Exposure and treatment-on-the-treated effects are out of scope for the first version, because they require additional assumptions and are easy to get wrong.

Implemented in Phase 1: SRM, covariate balance, Welch difference in means, stratified bootstrap, CUPED, and a calibration simulator. Implemented in Phase 2: a T-learner uplift model, Qini/AUUC, rank-bucket calibration, a fixed-budget policy with bootstrap uncertainty, and a FastAPI + React interface. Implemented in Phase 3: dollar budgets, a profit-versus-budget curve, and a ranked target export.

Planned: S-learner and propensity baselines, IPS/DR policy evaluation, policy regret, sequential monitoring, Bayesian readout, ratio metrics, power/MDE, guardrails, multiple-testing correction, and the Criteo scale case.

## 2. Notation and estimands

For unit `i`:

- `T_i in {0, 1}` is the treatment assignment.
- `Y_i` is the observed outcome.
- `X_i` is the vector of pre-treatment covariates.
- `Y_i(1)` and `Y_i(0)` are the potential outcomes.

The average treatment effect is

$$
\tau = \mathbb{E}[Y(1) - Y(0)].
$$

The conditional average treatment effect is

$$
\tau(x) = \mathbb{E}[Y(1) - Y(0) \mid X = x].
$$

A targeting policy is a function `pi: X -> {0, 1}`. Its value is the expected outcome if the policy decides who is treated:

$$
V(\pi) = \mathbb{E}[Y(1)\pi(X) + Y(0)(1 - \pi(X))].
$$

The decision problem is to choose a policy that maximizes incremental profit subject to a budget, not to maximize the average effect.

## 3. Experiment validation

### 3.1 Sample ratio mismatch

Compare observed assignment counts with expected counts using a chi-square goodness-of-fit test:

$$
\chi^2 = \sum_k \frac{(O_k - E_k)^2}{E_k}.
$$

A very small p-value, typically below 0.001, triggers an investigation. It does not automatically invalidate the experiment, because a broken randomization, a logging bug, or a legitimate traffic shift can all produce the same signal. The report shows the counts, expected counts, and p-value.

### 3.2 Covariate balance

For each covariate, compute the standardized mean difference:

$$
\text{SMD} = \frac{\bar{X}_t - \bar{X}_c}{\sqrt{(s_t^2 + s_c^2)/2}}.
$$

Absolute values below 0.1 are treated as balanced. Larger values are reported, not silently adjusted away.

### 3.3 Power and minimum detectable effect (planned)

Before the experiment, compute the minimum detectable effect for the planned sample size, allocation, baseline rate or variance, alpha, and power. After the experiment, report the achieved precision instead of pretending the study was powered for an effect it was not designed to detect. No MDE command exists yet.

### 3.4 Guardrails (planned)

Guardrail metrics use non-inferiority margins, not "not statistically significant." A guardrail passes only when the lower bound of its confidence interval is above the acceptable harm threshold. The report separates primary, secondary, and guardrail metrics. The Phase 1 readout has one primary outcome and no guardrail family.

## 4. Estimation

### 4.1 Difference in means (implemented)

For a continuous outcome, the primary estimate is the difference in means with a Welch confidence interval, which does not assume equal variances. For a binary outcome, the same estimator is used on the 0/1 outcome, with the corresponding standard error. The interval is normal-approximation, and the report labels it with the configured confidence level.

### 4.2 Bootstrap (implemented for the ATE)

The bootstrap is planned as the default for intervals on nonlinear quantities: Qini, policy value, profit, iROAS, and cost per incremental conversion. Resampling is stratified by treatment arm so that the allocation ratio is preserved in every replicate. The Phase 1 readout resamples within arm and reports a percentile interval for the ATE, using 2,000 replicates by default and a fixed seed. No interval is bootstrapped for the variance reduction.

### 4.3 Bayesian readout (planned)

For binary outcomes, use a Beta-Binomial model:

$$
p_t \sim \text{Beta}(a_t + y_t,\ b_t + n_t - y_t),
$$

with the same construction for control. The posterior difference is sampled directly. The report includes the probability that the treatment is better and the expected loss from choosing the wrong arm. The prior is weakly informative and stated in the config, not hidden in code. No Bayesian command exists yet.

### 4.4 CUPED (implemented)

CUPED uses a pre-treatment covariate `X` to reduce variance:

$$
\hat{\theta} = \frac{\operatorname{Cov}(Y, X)}{\operatorname{Var}(X)},
$$

$$
Y_i^{\text{adj}} = Y_i - \hat{\theta}(X_i - \bar{X}).
$$

The adjusted treatment effect is the difference in means of `Y_adj`. The empirical variance reduction is

$$
1 - \frac{\operatorname{Var}(Y^{\text{adj}})}{\operatorname{Var}(Y)}.
$$

For a single linear adjustment, this equals the squared correlation between `Y` and `X`, so it is a descriptive diagnostic, not an independent estimate. The covariate must be measured before treatment and must not be affected by it; the readout rejects a covariate that is not declared in the dataset's pre-treatment list. The report shows the correlation, theta, and the variance reduction.

`theta` is estimated on the analysed sample, which is what the Phase 1 report does, and the reported reduction is therefore in-sample and slightly optimistic on small samples. The library also accepts a training-fit theta for holdout evaluation. Cross-fitting is a possible extension.

### 4.5 Ratio metrics (planned)

For a ratio `R = \bar{Y} / \bar{X}`, use the delta method:

$$
\operatorname{Var}(R) \approx \frac{1}{n} \cdot
\frac{\operatorname{Var}(Y) + R^2\operatorname{Var}(X) - 2R\operatorname{Cov}(X,Y)}{\bar{X}^2}.
$$

This covers metrics such as revenue per session or clicks per impression. The report labels ratio metrics explicitly and does not treat them as simple means. No ratio-metric code exists yet.

### 4.6 Sequential monitoring (planned)

Repeated significance testing inflates the Type I error rate. The planned design is group sequential monitoring with O'Brien-Fleming boundaries and Lan-DeMets alpha spending. The number of looks and the spending function would be fixed before the experiment.

The report would show the naive and adjusted decision boundaries, and the simulation module would quantify the inflation from naive peeking. Always-valid confidence sequences are a possible extension, not part of the first version. Nothing in Phase 1 peeks or corrects for peeking.

### 4.7 Multiple testing (planned)

One primary metric is declared in advance. Secondary metrics would use Benjamini-Hochberg false discovery rate control. Guardrails would use Holm correction or Bonferroni. The report states which correction was applied to which family, and does not mix corrected and uncorrected p-values in the same table. Phase 1 reports a single primary outcome, so it applies no correction and says so in the caveats.

## 5. Uplift modeling (Phase 2 subset implemented)

The implemented model is a T-learner. The S-learner, propensity baseline, and off-policy evaluation are planned and are not used in any result.

### 5.1 T-learner (implemented)

Fit one outcome model per arm:

$$
\hat{\mu}_1(x) \approx \mathbb{E}[Y \mid X=x, T=1], \qquad
\hat{\mu}_0(x) \approx \mathbb{E}[Y \mid X=x, T=0],
$$

$$
\hat{\tau}(x) = \hat{\mu}_1(x) - \hat{\mu}_0(x).
$$

The implementation uses two `HistGradientBoostingClassifier` models with `early_stopping=False` and a shared random seed. The score is the difference between the two predicted probabilities of the positive outcome. Features are the declared pre-treatment balance covariates; categorical columns are one-hot encoded with unknown categories ignored.

The data is split 60% train, 20% validation, 20% holdout, stratified by treatment and outcome. Every split must contain both arms. The holdout is scored once, after model selection.

The T-learner can be unstable when one arm is much smaller than the other. The report shows the split sizes, but it does not include a formal stability diagnostic.

### 5.2 S-learner (planned)

Fit a single model with treatment as a feature:

$$
\hat{\mu}(x, t) \approx \mathbb{E}[Y \mid X=x, T=t],
$$

$$
\hat{\tau}(x) = \hat{\mu}(x, 1) - \hat{\mu}(x, 0).
$$

The S-learner shares strength across arms but can shrink heterogeneous effects toward a constant. It is not implemented. The planned comparison would use the same split and holdout as the T-learner.

### 5.3 Baselines (implemented and planned)

The implemented policy report compares the model with:

- **Random targeting:** choose the same number of units at random and use the expected incremental outcome at that budget.
- **Treat-all:** treat everyone and report full-holdout incremental profit.

The planned comparison adds a **propensity model** that estimates `P(Y=1 | X)` and ranks by that score. That baseline is the important one for showing whether uplift ranking beats response ranking, which selects sure things rather than persuadables. It is not implemented.

### 5.4 Model choice (implemented)

Two fixed candidates are compared on validation AUUC gain over the random line:

| Leaves | Learning rate | L2 regularization |
| ---: | ---: | ---: |
| 15 | 0.06 | 1.0 |
| 31 | 0.08 | 1.0 |

Both use `max_iter=200` and `min_samples_leaf=40`. The best candidate is refit on train plus validation, then scored on holdout. The holdout is never used to choose the model or its hyperparameters.

The implementation uses scikit-learn's histogram gradient boosting, not LightGBM. No deep learning and no distributed training. The candidate grid is small and fixed; there is no broad hyperparameter search.

### 5.5 Calibration (implemented as rank buckets)

Ranking and calibration are different properties. A model can produce a good Qini curve while its predicted uplift is systematically wrong.

The implementation sorts the holdout by predicted uplift into five equal-count rank buckets. For each bucket it reports:

- the number of customers and treated share,
- the mean predicted uplift,
- the observed difference in outcomes between treated and control, with a 95% Welch interval.

Q1 is the lowest predicted uplift and Q5 is the highest. These are rank buckets, not causal strata and not deciles. The current Hillstrom result is non-monotone, which is evidence that the model does not separate persuadable customers well on that holdout.

## 6. Evaluation (holdout subset implemented)

Phase 1 reports a single ATE and its interval. Phase 2 adds Qini, AUUC, rank-bucket calibration, and a fixed-budget policy value. IPS/DR policy evaluation, reliability diagnostics, and policy regret are planned.

### 6.1 Qini curve (implemented)

Sort observations by predicted uplift in descending order. For the top `k` observations, let:

- `n_t(k)` and `n_c(k)` be the number of treated and control units,
- `y_t(k)` and `y_c(k)` be the cumulative number of positive outcomes.

The cumulative incremental outcome is

$$
Q(k) = y_t(k) - y_c(k) \cdot \frac{n_t(k)}{n_c(k)}.
$$

The plotted model curve is `Q(k) / n`, so the vertical axis is incremental outcomes per customer. The random line is the straight line from `(0, 0)` to the overall incremental rate `Q(n) / n`.

The Qini coefficient is the relative area gain over that random line:

$$
\text{Qini} = \frac{\text{AUUC} - \text{random AUUC}}{\text{random AUUC}}.
$$

A value of 0 is random ranking, 1 captures the whole incremental outcome at the top, and negative means worse than random. The implementation reports the raw coefficient and does not divide by a scikit-uplift reference curve. It also does not yet attach a bootstrap band. The actual Hillstrom value is 0.004, which is close to random.

### 6.2 Uplift curve and AUUC (implemented)

The implementation integrates the model curve over the customer fractions with the trapezoid rule:

$$
\text{AUUC} = \int_0^1 \frac{Q(k)}{n} \, d\left(\frac{k}{n}\right).
$$

The random AUUC is the area under the straight random line, `0.5 * Q(n) / n`. Qini is derived from the two areas. The report shows both AUUC and Qini because they answer related but not identical questions.

### 6.3 Policy value (implemented, direct holdout contrast)

For a fixed budget fraction, the policy selects the top `k = ceil(fraction * n)` holdout customers by predicted uplift. The incremental outcome on that selected set is

$$
\hat{\Delta} = \sum_{i \in S, T_i=1} Y_i
- \sum_{i \in S, T_i=0} Y_i \cdot \frac{n_{t,S}}{n_{c,S}}.
$$

Value is `value_per_conversion * Delta`, cost is `k * cost_per_contact`, profit is value minus cost, and ROI is profit divided by cost when cost is positive. Every selected set must contain both arms.

This is a direct observed-outcome contrast, not IPS or DR. It uses the randomized holdout and is valid for the selected set, but it does not adjust for covariate imbalance inside that set. The 95% bootstrap interval resamples outcomes within arm and conditions on the selected customers. It does not include model-selection uncertainty, and it is not a confidence interval for the difference between the model and random policies.

The same pricing routine is re-run across 20 budget fractions to produce the descriptive profit curve described in section 7.1.

The planned IPS/DR estimators would use the known assignment probability and outcome models. The planned reliability table would report Kish effective sample size, maximum weight, interval width relative to the estimate, and weighted covariate imbalance. None of that is implemented.

### 6.4 Policy regret (planned)

In simulation, the true policy value is known. Regret is

$$
\text{regret} = V(\pi^*) - V(\hat{\pi}),
$$

where `pi*` is the best policy under the known potential outcomes. Regret would be reported as a distribution over replications, not a single number. The Phase 1 simulator does not produce potential outcomes for this, so no regret result exists.

## 7. Budget-constrained policy (fraction and dollar budget implemented)

Two budget inputs are accepted: a fraction `f` of the holdout via `--budget`, or a dollar budget `B` via `--budget-dollars`. They are mutually exclusive. A dollar budget converts to a contact count through the homogeneous cost per contact `c`:

$$
k = \min\left(n,\ \left\lceil \frac{B}{c} \right\rceil\right),
\qquad f_{\text{eff}} = \frac{k}{n}.
$$

A fraction budget uses `k = ceil(f * n)`. In both cases the policy ranks customers by predicted uplift and treats the top `k`, with a stable sort for ties. Every selected set must contain both arms.

Cost is homogeneous per contact, and value is homogeneous per incremental outcome unit. For the Hillstrom `visit` outcome, `--value 2.0` means $2 per incremental visit, and `--cost 0.05` means $0.05 per contact. The parameter name `value_per_conversion` is historical; it is applied to whatever outcome is configured.

The incremental outcome, value, cost, and profit are

$$
\Delta = \sum_{i \in S, T_i=1} Y_i - \sum_{i \in S, T_i=0} Y_i \cdot \frac{n_{t,S}}{n_{c,S}},
$$

$$
\text{value} = v \cdot \Delta, \qquad \text{cost} = c \cdot k, \qquad \text{profit} = \text{value} - \text{cost}.
$$

ROI is `profit / cost` when cost is positive. The 95% bootstrap interval for profit resamples outcomes within arm and conditions on the selected customers.

The report compares the model with random targeting at the same effective fraction and with treat-all at 100% of the holdout. Treat-all is a different budget, not a like-for-like competitor.

### 7.1 Profit versus budget

The profit curve re-prices the same fitted holdout ranking at 20 evenly spaced fractions from 0.05 to 1.00. It reports customers, incremental outcome, value, cost, profit, and ROI at each point. Each point uses the same direct holdout contrast as the policy, without a bootstrap interval. The points are correlated because they share customers and outcomes, and the curve is descriptive of this holdout, not a causal response surface for a future campaign. A non-monotone curve is possible and is reported as-is.

### 7.2 Target export

The `target` command fits the model once, selects the top `k` holdout customers under the same budget rule, and writes a CSV with `rank`, `row`, and `predicted_uplift`. `row` is the original dataframe index of the holdout row, so the export joins back to the source frame. The export contains holdout rows only; the fitted model itself is not persisted or published.

Not implemented: a value/cost sensitivity grid, break-even value, a risk-adjusted lower-bound policy, a propensity baseline, IPS/DR policy evaluation, and policy regret. Those remain Phase 2/4 work.

## 8. Simulation design (implemented, Phase 1 subset)

Phase 1 simulates independent Bernoulli outcomes. For unit `i`:

$$
p_0(x_i) = p_c, \qquad p_1(x_i) = \operatorname{clip}(p_c + \tau_0 + \gamma x_i,\ 0, 1),
$$

$$
T_i \sim \operatorname{Bernoulli}(e), \qquad Y_i \sim \operatorname{Bernoulli}(p_{T_i}(x_i)),
$$

with `x_i` drawn uniformly on `[0, 1]`. This gives a known true ATE of `tau_0 + gamma / 2`. The continuous-outcome and logistic-model variants described in earlier drafts are not implemented.

The five scenarios that exist are:

| Scenario | Purpose |
| --- | --- |
| Null (`tau_0 = 0`, `gamma = 0`) | Type I error at alpha 0.05 |
| Constant positive effect (`+0.03`) | Power and interval coverage |
| Heterogeneous effect (`gamma = 0.04`, average `+0.02`) | ATE calibration when the effect varies with a pre-treatment score |
| Harmful (`-0.02`) | Sign handling and power |
| Unbalanced allocation (`e = 0.2`) | Precision loss under unequal allocation |

Each replication runs the same Welch estimator used on real data, at n = 10,000 and seed 42. The headline run uses 5,000 replications per scenario and records the mean estimate, bias, empirical standard error, mean estimated standard error, interval coverage, rejection rate, and the Monte Carlo standard error of both rates. Scenarios are seeded as `seed + index`, so adding a scenario does not change the earlier ones.

The simulator does **not** produce potential outcomes for Qini, calibration, policy value, or regret. Phase 2 evaluates those on real holdout labels from Hillstrom instead; the simulator still does not support them.

## 9. Assumptions and limitations

- **Randomization:** treatment is assigned independently of potential outcomes. The real datasets satisfy this by design.
- **No interference:** one unit's treatment does not change another unit's outcome. This is an approximation in ad auctions and email campaigns.
- **Consistency:** the observed outcome equals the potential outcome under the assigned treatment.
- **Positivity:** both arms have nonzero probability for the covariate values in the analysis.
- **ITT, not exposure:** Criteo's `exposure` column is post-treatment. The main analysis uses `treatment`. Conditioning on exposure would break randomization.
- **CUPED:** requires a pre-treatment covariate and a roughly linear relationship. The report checks the correlation and the empirical variance reduction.
- **Uplift identification (implemented with caveats):** CATE estimates rely on randomization plus the observed covariates. They are not a substitute for a new experiment when the population or campaign changes.
- **Costs and values (implemented with caveats):** the policy uses assumed costs and values supplied on the command line. No sensitivity grid or break-even analysis is included, so a profit number is conditional on those assumptions.
- **Criteo features:** the 12 anonymized features `f0` through `f11` carry no claimed business meaning.
- **Hillstrom arms:** the primary contrast is any e-mail versus no e-mail. The Mens versus Womens contrast is secondary and not in the Phase 1 report.
- **No new causal method:** the contribution is the end-to-end decision pipeline, the calibration checks, and the simulation evidence. The Phase 1 and Phase 2 code use standard estimators; the benchmark and holdout evaluation are what make the claims checkable.

## 10. Reproducibility

- Fixed seeds for the simulation and the Hillstrom bootstrap.
- Checksums for every downloaded dataset, verified on fetch and again before analysis.
- `uv.lock` committed.
- Benchmark outputs written to JSON and rendered into Markdown from the same payload.
- Full calibration suite: `uv run upliftlab simulate --scenario all --replications 5000 --out results/bench.json --markdown docs/results.md --force`.
- Uplift and policy case study: `uv run upliftlab uplift hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/uplift.json --markdown reports/uplift.md --force`.
- Target export: `uv run upliftlab target hillstrom --outcome visit --budget-dollars 128 --cost 0.05 --out results/targets.csv --force`.
- Local API and UI: `docker compose up --build`, then `http://localhost:8000` and `GET /api/health`.
- Fast tests run in CI without downloading data.

## References

- Deng, Xu, Kohavi, Walker (2013). Improving the Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment Data.
- Radcliffe (2007). Using Control Groups to Target on Predicted Lift.
- Devriendt, Guns, Verbeke (2020). Learning to Rank for Uplift Modeling.
- Diemert, Betlei, Renaudin, Amini (2018). A Large Scale Benchmark for Uplift Modeling.
- Howard, Ramdas, McAuliffe, Sekhon (2021). Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences.
