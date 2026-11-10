"""Validation: sample-ratio mismatch and covariate balance."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from upliftlab.errors import AnalysisError
from upliftlab.experiment.estimators import coerce_binary_treatment
from upliftlab.results import BalanceRow, SRMResult


def srm_test(
    counts: Sequence[int],
    *,
    labels: Sequence[str] | None = None,
    expected: Sequence[float] | None = None,
    alpha: float = 0.001,
) -> SRMResult:
    """Chi-square SRM check, with an exact binomial fallback for two small arms."""
    try:
        raw = np.asarray(counts, dtype=float)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"SRM counts must be numeric: {exc}") from exc
    if raw.ndim != 1 or raw.size < 2:
        raise AnalysisError("SRM needs at least two arms")
    if not np.isfinite(raw).all():
        raise AnalysisError("SRM counts must be finite")
    if (raw < 0).any():
        raise AnalysisError("SRM counts must be non-negative")
    if not np.equal(raw, np.floor(raw)).all():
        raise AnalysisError("SRM counts must be integers")
    observed = raw.astype(np.int64)
    total = int(observed.sum())
    if total == 0:
        raise AnalysisError("SRM counts sum to zero")
    if not 0.0 < alpha < 1.0:
        raise AnalysisError("alpha must be strictly between 0 and 1")

    arm_labels = (
        tuple(labels) if labels is not None else tuple(str(i) for i in range(len(observed)))
    )
    if len(arm_labels) != len(observed):
        raise AnalysisError("SRM labels and counts must have the same length")

    if expected is None:
        proportions = np.full(len(observed), 1.0 / len(observed))
    else:
        proportions = np.asarray(expected, dtype=float)
        if proportions.shape != observed.shape:
            raise AnalysisError("SRM expected proportions and counts must have the same length")
        if not np.isfinite(proportions).all():
            raise AnalysisError("SRM expected proportions must be finite")
        if (proportions <= 0).any():
            raise AnalysisError("SRM expected proportions must be positive")
        if not np.isclose(proportions.sum(), 1.0, atol=1e-8):
            raise AnalysisError("SRM expected proportions must sum to 1")
        proportions = proportions / proportions.sum()

    expected_counts = proportions * total
    expected_counts[-1] = total - expected_counts[:-1].sum()
    if len(observed) == 2 and (expected_counts < 5).any():
        result = stats.binomtest(int(observed[0]), total, p=float(proportions[0]))
        return SRMResult(
            labels=arm_labels,
            counts=tuple(int(value) for value in observed),
            expected_counts=tuple(float(value) for value in expected_counts),
            chi_square=float("nan"),
            p_value=float(result.pvalue),
            method="binomial",
            alpha=alpha,
            detected=bool(result.pvalue < alpha),
        )

    chi_square, p_value = stats.chisquare(observed, f_exp=expected_counts)
    return SRMResult(
        labels=arm_labels,
        counts=tuple(int(value) for value in observed),
        expected_counts=tuple(float(value) for value in expected_counts),
        chi_square=float(chi_square),
        p_value=float(p_value),
        method="chi-square",
        alpha=alpha,
        detected=bool(p_value < alpha),
    )


def _standardized_mean_difference(
    values: np.ndarray,
    treatment: np.ndarray,
) -> tuple[float, float, float]:
    treated = values[treatment == 1]
    control = values[treatment == 0]
    if treated.size < 2 or control.size < 2:
        raise AnalysisError("balance needs at least two observations per arm")
    treated_mean = float(np.mean(treated))
    control_mean = float(np.mean(control))
    pooled = float(np.sqrt((np.var(treated, ddof=1) + np.var(control, ddof=1)) / 2.0))
    if pooled == 0.0:
        smd = 0.0 if treated_mean == control_mean else float("inf")
    else:
        smd = (treated_mean - control_mean) / pooled
    return treated_mean, control_mean, float(smd)


def compute_balance(
    frame: pd.DataFrame,
    treatment_column: str,
    covariates: Sequence[str],
    *,
    categorical: Sequence[str] = (),
) -> tuple[BalanceRow, ...]:
    """Standardized mean differences; categoricals expand to dummy proportions."""
    if treatment_column not in frame.columns:
        raise AnalysisError(f"missing treatment column: {treatment_column}")
    treatment = coerce_binary_treatment(frame[treatment_column].to_numpy())

    rows: list[BalanceRow] = []
    categorical_set = set(categorical)
    for covariate in covariates:
        if covariate not in frame.columns:
            raise AnalysisError(f"missing balance covariate: {covariate}")
        series = frame[covariate]
        if series.isna().any():
            raise AnalysisError(f"balance covariate {covariate} contains missing values")
        if covariate in categorical_set:
            dummies = pd.get_dummies(series, prefix=covariate, dtype=float)
            for dummy in dummies.columns.to_list():
                name = str(dummy)
                values = dummies[dummy].to_numpy(dtype=float)
                treated_mean, control_mean, smd = _standardized_mean_difference(values, treatment)
                rows.append(
                    BalanceRow(
                        covariate=name,
                        treated_mean=treated_mean,
                        control_mean=control_mean,
                        smd=smd,
                        n_treated=int((treatment == 1).sum()),
                        n_control=int((treatment == 0).sum()),
                    )
                )
        else:
            try:
                values = pd.to_numeric(series, errors="raise").to_numpy(dtype=float)
            except (TypeError, ValueError) as exc:
                raise AnalysisError(f"{covariate}: balance covariate must be numeric") from exc
            if not np.isfinite(values).all():
                raise AnalysisError(f"{covariate}: balance covariate contains non-finite values")
            treated_mean, control_mean, smd = _standardized_mean_difference(values, treatment)
            rows.append(
                BalanceRow(
                    covariate=covariate,
                    treated_mean=treated_mean,
                    control_mean=control_mean,
                    smd=smd,
                    n_treated=int((treatment == 1).sum()),
                    n_control=int((treatment == 0).sum()),
                )
            )

    return tuple(sorted(rows, key=lambda row: abs(row.smd), reverse=True))
