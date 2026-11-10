"""Difference-in-means estimation and stratified bootstrap."""

from __future__ import annotations

import numpy as np
from scipy import stats

from upliftlab.errors import AnalysisError
from upliftlab.results import ATEResult, BootstrapResult


def coerce_binary_treatment(values: np.ndarray) -> np.ndarray:
    """Validate the original values before casting, so 0.5 cannot become 0."""
    array = np.asarray(values)
    if array.ndim != 1:
        raise AnalysisError("treatment must be one-dimensional")
    if array.dtype == np.bool_:
        return array.astype(np.int8)
    if not np.issubdtype(array.dtype, np.number):
        raise AnalysisError("treatment must be numeric")
    numeric = array.astype(float)
    if not np.isfinite(numeric).all():
        raise AnalysisError("treatment contains non-finite values")
    if not np.isin(numeric, [0.0, 1.0]).all():
        raise AnalysisError("treatment must be binary (0 or 1)")
    return numeric.astype(np.int8)


def _validate_inputs(y: np.ndarray, treatment: np.ndarray) -> None:
    if y.ndim != 1 or treatment.ndim != 1:
        raise AnalysisError("outcome and treatment must be one-dimensional")
    if y.size != treatment.size:
        raise AnalysisError("outcome and treatment must have the same length")
    if not np.issubdtype(treatment.dtype, np.number):
        raise AnalysisError("treatment must be numeric")
    if not np.isin(treatment, [0, 1]).all():
        raise AnalysisError("treatment must be binary")
    if not np.isfinite(y).all():
        raise AnalysisError("outcome contains non-finite values")
    if int((treatment == 1).sum()) < 2 or int((treatment == 0).sum()) < 2:
        raise AnalysisError("each arm needs at least two observations")
    if (
        float(np.var(y[treatment == 1], ddof=1)) == 0.0
        and float(np.var(y[treatment == 0], ddof=1)) == 0.0
    ):
        raise AnalysisError("outcome has zero variance in both arms")


def difference_in_means(
    y: np.ndarray,
    treatment: np.ndarray,
    *,
    alpha: float = 0.05,
) -> ATEResult:
    """Welch difference in means with a normal-approximation confidence interval."""
    y = np.asarray(y, dtype=float)
    treatment = coerce_binary_treatment(treatment)
    _validate_inputs(y, treatment)
    if not 0.0 < alpha < 1.0:
        raise AnalysisError("alpha must be strictly between 0 and 1")

    treated = y[treatment == 1]
    control = y[treatment == 0]
    n_treated = int(treated.size)
    n_control = int(control.size)
    estimate = float(np.mean(treated) - np.mean(control))

    var_treated = float(np.var(treated, ddof=1))
    var_control = float(np.var(control, ddof=1))
    variance = var_treated / n_treated + var_control / n_control
    if variance <= 0.0:
        raise AnalysisError("outcome has zero variance in both arms")

    standard_error = float(np.sqrt(variance))
    numerator = variance**2
    denominator = (var_treated / n_treated) ** 2 / (n_treated - 1) + (
        var_control / n_control
    ) ** 2 / (n_control - 1)
    degrees_of_freedom = float(numerator / denominator)
    t_statistic = estimate / standard_error
    p_value = float(2.0 * stats.t.sf(abs(t_statistic), degrees_of_freedom))
    critical = float(stats.t.ppf(1.0 - alpha / 2.0, degrees_of_freedom))

    return ATEResult(
        estimate=estimate,
        standard_error=standard_error,
        ci_low=estimate - critical * standard_error,
        ci_high=estimate + critical * standard_error,
        p_value=p_value,
        alpha=alpha,
        n_treated=n_treated,
        n_control=n_control,
        method="welch",
    )


def bootstrap_difference_in_means(
    y: np.ndarray,
    treatment: np.ndarray,
    *,
    n_bootstrap: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> BootstrapResult:
    """Percentile bootstrap, resampling independently within each arm."""
    y = np.asarray(y, dtype=float)
    treatment = coerce_binary_treatment(treatment)
    _validate_inputs(y, treatment)
    if n_bootstrap < 100:
        raise AnalysisError("n_bootstrap must be at least 100")
    if not 0.0 < alpha < 1.0:
        raise AnalysisError("alpha must be strictly between 0 and 1")

    treated = y[treatment == 1]
    control = y[treatment == 0]
    rng = np.random.default_rng(seed)
    draws = np.empty(n_bootstrap, dtype=float)
    for index in range(n_bootstrap):
        treated_sample = rng.choice(treated, size=treated.size, replace=True)
        control_sample = rng.choice(control, size=control.size, replace=True)
        draws[index] = float(np.mean(treated_sample) - np.mean(control_sample))

    low, high = np.quantile(draws, [alpha / 2.0, 1.0 - alpha / 2.0])
    return BootstrapResult(
        estimate=float(np.mean(treated) - np.mean(control)),
        ci_low=float(low),
        ci_high=float(high),
        n_bootstrap=n_bootstrap,
        seed=seed,
        alpha=alpha,
    )
