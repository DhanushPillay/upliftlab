# Methodology

This document records the statistical contract for `upliftlab`. It covers the estimands, estimators, evaluation metrics, budget rule, simulation design, and assumptions. The goal is to make every number in the report traceable to a definition.

Sections are labelled by phase. **Implemented** means the code exists and the Phase 1 benchmark exercises it. **Planned** means the method is specified but the code does not exist yet, so no result in [results.md](results.md) uses it.

## 1. Scope

The project handles randomized experiments with:

- a binary treatment assignment,
- one or more outcomes (binary, continuous, or dollar-valued),
- pre-treatment covariates,
- a decision about who should receive the treatment under a budget.

The main estimand is the intent-to-treat (ITT) effect. Exposure and treatment-on-the-treated effects are out of scope for the first version, because they require additional assumptions and are easy to get wrong.

Implemented in Phase 1: SRM, covariate balance, Welch difference in means, stratified bootstrap, CUPED, and a calibration simulator. Everything about uplift ranking, policy value, and budget allocation is planned for Phase 2/3.

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

## 5. Uplift modeling (planned)

None of this section is implemented. It documents the intended Phase 2 contract so the Phase 1 benchmark is not mistaken for an uplift result.

### 5.1 T-learner

Fit one outcome model per arm:

$$
\hat{\mu}_1(x) \approx \mathbb{E}[Y \mid X=x, T=1], \qquad
\hat{\mu}_0(x) \approx \mathbb{E}[Y \mid X=x, T=0],
$$

$$
\hat{\tau}(x) = \hat{\mu}_1(x) - \hat{\mu}_0(x).
$$

The T-learner is flexible but can be unstable when one arm is much smaller than the other. The report shows arm sizes and model diagnostics.

### 5.2 S-learner

Fit a single model with treatment as a feature:

$$
\hat{\mu}(x, t) \approx \mathbb{E}[Y \mid X=x, T=t],
$$

$$
\hat{\tau}(x) = \hat{\mu}(x, 1) - \hat{\mu}(x, 0).
$$

The S-learner shares strength across arms but can shrink heterogeneous effects toward a constant. Both models are compared on the same holdout split.

### 5.3 Baselines

Every uplift model is compared with:

- **Random targeting:** choose the same number of units at random.
- **Treat-all:** treat everyone.
- **Propensity model:** estimate `P(Y=1 | X)` and rank by that score.

The propensity baseline is the important one. It represents the common but wrong practice of targeting the customers most likely to convert, which selects sure things rather than persuadables.

### 5.4 Model choice (planned)

The planned implementation uses LightGBM for both learners. It handles nonlinearities and interactions on tabular data, runs on CPU, and is fast enough for a 14M-row dataset in memory. No deep learning and no distributed training. Hyperparameters are fixed in a config and tuned only on a validation split, never on the holdout.

### 5.5 Calibration (planned)

Ranking and calibration are different properties. A model can produce a good Qini curve while its predicted uplift is systematically too large. The report bins the holdout by predicted uplift and compares the mean prediction with the observed difference in outcomes between treated and control within each bin. Each bin gets a confidence interval. The calibration table is a required output, not an optional diagnostic.

## 6. Evaluation (planned)

Phase 1 reports a single ATE and its interval. The ranking metrics below are specified for Phase 2 and are not computed by any current command.

### 6.1 Qini curve

Sort observations by predicted uplift in descending order. For the top `k` observations, let:

- `n_t(k)` and `n_c(k)` be the number of treated and control units,
- `y_t(k)` and `y_c(k)` be the cumulative number of positive outcomes.

The Qini curve is

$$
Q(k) = y_t(k) - y_c(k) \cdot \frac{n_t(k)}{n_c(k)}.
$$

The Qini coefficient is the area between `Q(k)` and the diagonal from `(0, 0)` to `(N, Q(N))`, divided by the area between the reference Qini curve and that diagonal. The reference curve is built by ranking on the observed individual treatment effect proxy `y_i T_i - y_i (1 - T_i)`, following the reference implementation in scikit-uplift. It is a reference, not a true upper bound: it is computed from the same noisy holdout labels, so a normalized Qini can exceed 1. The report labels it as a reference, clips only the plotted curve for display, and always shows the raw Qini/AUUC with a bootstrap band and Qini at fixed fractions such as 10% and 20%.

The implementation will be validated against hand-computed examples and the scikit-uplift reference on the same inputs. Small differences in normalization are documented rather than hidden.

### 6.2 Uplift curve and AUUC

The uplift curve uses

$$
U(k) = \left(\frac{y_t(k)}{n_t(k)} - \frac{y_c(k)}{n_c(k)}\right) \cdot k.
$$

The normalized area under the uplift curve (AUUC) is computed against the perfect uplift curve in the same way as the Qini coefficient. Qini and AUUC answer related but not identical questions, so both are reported.

### 6.3 Policy value

For a deterministic policy `pi`, the inverse propensity score (IPS) estimate on a randomized holdout is

$$
\hat{V}_{\text{IPS}}(\pi) = \frac{1}{n}\sum_i
\left[
\frac{T_i Y_i \pi(X_i)}{e}
+
\frac{(1-T_i) Y_i (1-\pi(X_i))}{1-e}
\right],
$$

where `e` is the known assignment probability.

The doubly robust (DR) estimate uses outcome models `mu_0` and `mu_1`:

$$
\hat{V}_{\text{DR}}(\pi) = \frac{1}{n}\sum_i
\left[
\hat{\mu}_0(X_i) + \pi(X_i)(\hat{\mu}_1(X_i) - \hat{\mu}_0(X_i))
+
\frac{T_i (Y_i - \hat{\mu}_1(X_i)) \pi(X_i)}{e}
+
\frac{(1-T_i)(Y_i - \hat{\mu}_0(X_i))(1-\pi(X_i))}{1-e}
\right].
$$

Policy value is evaluated on the holdout only. The model that produced the scores never sees the holdout outcomes. Confidence intervals come from a stratified bootstrap.

For binary randomized treatment, the weights are bounded by `1 / min(e, 1-e)`, so clipping is unnecessary and only adds bias. Clipping is reserved for stochastic policies or estimated propensities; when used, the report shows the clip fraction and a bias sensitivity check.

The estimate is published only if its diagnostics pass. Otherwise the report prints "estimate unreliable" and does not present three significant digits.

| Diagnostic | Warn | Fail |
| --- | --- | --- |
| Kish effective sample size, per arm | below 10% of `n` | below 100 |
| Maximum weight | above 10 | above 20 |
| CI half-width relative to the estimate | above 0.25 | above 0.5 |
| Weighted covariate imbalance | any abs(SMD) above 0.1 | any abs(SMD) above 0.2 |

The report emits `reliability: ok | warn | fail` with the reasons, plus the weight histogram, the maximum weight, the ESS, and treatment rate by propensity decile. Random and treat-all baselines always appear in the same table. A failed reliability check is a result, not something to hide.

### 6.4 Policy regret

In simulation, the true policy value is known. Regret is

$$
\text{regret} = V(\pi^*) - V(\hat{\pi}),
$$

where `pi*` is the best policy under the known potential outcomes. Regret is reported as a distribution over replications, not a single number.

## 7. Budget-constrained policy (planned)

The planned rule assumes a homogeneous cost `c` per treated unit and a fixed budget `B`. The number of units that can be treated is

$$
k = \left\lfloor \frac{B}{c} \right\rfloor.
$$

The policy ranks units by predicted uplift and treats the top `k`. Ties are broken by a fixed, documented rule.

The incremental conversions relative to no campaign are

$$
\Delta = V(\pi) - V(0),
$$

where `V(0)` is the expected outcome when nobody is treated. Incremental revenue is `value * Delta`, campaign cost is `c * k`, and incremental profit is

$$
\text{profit} = \text{value} \cdot \Delta - c \cdot k.
$$

The incremental return on ad spend is

$$
\text{iROAS} = \frac{\text{value} \cdot \Delta}{c \cdot k}.
$$

The cost per incremental conversion is `c * k / Delta`. All four quantities get bootstrap intervals.

The report includes:

- the profit-versus-budget curve,
- the same curve for treat-all, random, and propensity targeting,
- a sensitivity grid over `value` and `c`,
- the break-even value per conversion,
- a risk-adjusted variant that maximizes the lower confidence bound of profit rather than the point estimate.

The risk-adjusted variant is a decision aid, not a claim that the lower bound is the true profit. No `target` command exists yet.

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

The simulator does **not** produce potential outcomes for Qini, calibration, policy value, or regret. Those require the Phase 2 uplift layer and are not measured.

## 9. Assumptions and limitations

- **Randomization:** treatment is assigned independently of potential outcomes. The real datasets satisfy this by design.
- **No interference:** one unit's treatment does not change another unit's outcome. This is an approximation in ad auctions and email campaigns.
- **Consistency:** the observed outcome equals the potential outcome under the assigned treatment.
- **Positivity:** both arms have nonzero probability for the covariate values in the analysis.
- **ITT, not exposure:** Criteo's `exposure` column is post-treatment. The main analysis uses `treatment`. Conditioning on exposure would break randomization.
- **CUPED:** requires a pre-treatment covariate and a roughly linear relationship. The report checks the correlation and the empirical variance reduction.
- **Uplift identification (planned):** CATE estimates would rely on randomization plus the observed covariates. They are not a substitute for a new experiment when the population or campaign changes.
- **Costs and values (planned):** the budget model uses assumed costs and values. The sensitivity analysis would be part of the result, not an appendix.
- **Criteo features:** the 12 anonymized features `f0` through `f11` carry no claimed business meaning.
- **Hillstrom arms:** the primary contrast is any e-mail versus no e-mail. The Mens versus Womens contrast is secondary and not in the Phase 1 report.
- **No new causal method:** the contribution is the end-to-end decision pipeline, the calibration checks, and the simulation evidence. The Phase 1 code uses standard estimators; the benchmark is what makes the claims checkable.

## 10. Reproducibility

- Fixed seeds for the simulation and the Hillstrom bootstrap.
- Checksums for every downloaded dataset, verified on fetch and again before analysis.
- `uv.lock` committed.
- Benchmark outputs written to JSON and rendered into Markdown from the same payload.
- Full calibration suite: `uv run upliftlab simulate --scenario all --replications 5000 --out results/bench.json --markdown docs/results.md --force`.
- Fast tests run in CI without downloading data.

## References

- Deng, Xu, Kohavi, Walker (2013). Improving the Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment Data.
- Radcliffe (2007). Using Control Groups to Target on Predicted Lift.
- Devriendt, Guns, Verbeke (2020). Learning to Rank for Uplift Modeling.
- Diemert, Betlei, Renaudin, Amini (2018). A Large Scale Benchmark for Uplift Modeling.
- Howard, Ramdas, McAuliffe, Sekhon (2021). Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences.
