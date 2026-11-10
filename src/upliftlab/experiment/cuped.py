"""CUPED variance reduction with a pre-treatment covariate."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from upliftlab.errors import AnalysisError
from upliftlab.experiment.estimators import coerce_binary_treatment, difference_in_means
from upliftlab.results import CUPEDResult


def cuped_ate(
    frame: pd.DataFrame,
    treatment_column: str,
    outcome_column: str,
    covariate_column: str,
    *,
    theta: float | None = None,
    alpha: float = 0.05,
) -> CUPEDResult:
    """Estimate theta from the analysed sample, then compare raw and adjusted ATEs.

    Pass a training-fit ``theta`` when applying CUPED to a holdout so the
    covariate-outcome relation is not refit on the evaluation rows. The
    variance reduction is descriptive: theta is not cross-fitted here, so the
    reduction can be slightly optimistic on small samples.
    """
    for column in (treatment_column, outcome_column, covariate_column):
        if column not in frame.columns:
            raise AnalysisError(f"missing column: {column}")

    try:
        treatment = coerce_binary_treatment(frame[treatment_column].to_numpy())
        y = pd.to_numeric(frame[outcome_column], errors="raise").to_numpy(dtype=float)
        x = pd.to_numeric(frame[covariate_column], errors="raise").to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"CUPED columns must be numeric: {exc}") from exc

    if not np.isfinite(y).all():
        raise AnalysisError(f"{outcome_column}: CUPED outcome contains non-finite values")
    if not np.isfinite(x).all():
        raise AnalysisError(f"{covariate_column}: CUPED covariate contains non-finite values")

    if theta is None:
        variance_x = float(np.var(x, ddof=1))
        if variance_x == 0.0:
            raise AnalysisError(f"{covariate_column}: CUPED covariate has zero variance")
        covariance = float(np.cov(y, x, ddof=1)[0, 1])
        theta_estimate = covariance / variance_x
    else:
        if not math.isfinite(theta):
            raise AnalysisError("theta must be finite")
        theta_estimate = float(theta)

    adjusted_y = y - theta_estimate * (x - float(np.mean(x)))
    raw = difference_in_means(y, treatment, alpha=alpha)
    adjusted = difference_in_means(adjusted_y, treatment, alpha=alpha)

    variance_y = float(np.var(y, ddof=1))
    variance_adjusted = float(np.var(adjusted_y, ddof=1))
    variance_reduction = 1.0 - variance_adjusted / variance_y if variance_y > 0.0 else 0.0
    correlation = float(np.corrcoef(y, x)[0, 1]) if variance_y > 0.0 else 0.0

    return CUPEDResult(
        theta=float(theta_estimate),
        raw=raw,
        adjusted=adjusted,
        variance_reduction=float(variance_reduction),
        correlation=correlation,
    )
