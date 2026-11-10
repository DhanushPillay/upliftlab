"""Ranking and policy evaluation for out-of-sample uplift scores."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from upliftlab.errors import AnalysisError
from upliftlab.experiment.estimators import difference_in_means
from upliftlab.uplift.types import CurvePoint, PolicyResult, SegmentRow, UpliftMetrics

_CURVE_POINTS = 101


def _total_incremental(y: np.ndarray, treatment: np.ndarray) -> float:
    treated = treatment == 1
    n_treated = int(treated.sum())
    n_control = int((~treated).sum())
    if n_treated == 0 or n_control == 0:
        raise AnalysisError("uplift evaluation needs both treatment arms")
    return float(y[treated].sum() - y[~treated].sum() * n_treated / n_control)


def qini_metrics(
    y: np.ndarray,
    treatment: np.ndarray,
    score: np.ndarray,
    *,
    n_points: int = _CURVE_POINTS,
) -> tuple[UpliftMetrics, tuple[CurvePoint, ...]]:
    """Cumulative incremental curve with a normalized Qini coefficient.

    The curve is cumulative incremental outcomes per customer. The random
    baseline is the straight line from zero to the overall incremental rate.
    Qini is the relative area gain over that line, so 0 is random ranking and
    1 captures the whole incremental outcome at the top of the ranking.
    """
    y = np.asarray(y, dtype=float)
    treatment = np.asarray(treatment, dtype=np.int8)
    score = np.asarray(score, dtype=float)
    if y.ndim != 1 or treatment.ndim != 1 or score.ndim != 1:
        raise AnalysisError("uplift evaluation inputs must be one-dimensional")
    if not (y.size == treatment.size == score.size):
        raise AnalysisError("uplift evaluation inputs must have the same length")
    if not np.isfinite(score).all():
        raise AnalysisError("uplift scores contain non-finite values")
    if n_points < 2:
        raise AnalysisError("curve needs at least two points")

    total_incremental = _total_incremental(y, treatment)
    n = y.size
    order = np.argsort(-score, kind="stable")
    t_sorted = treatment[order] == 1
    y_sorted = y[order]
    cum_treated = np.cumsum(t_sorted)
    cum_control = np.cumsum(~t_sorted)
    cum_treated_y = np.cumsum(y_sorted * t_sorted)
    cum_control_y = np.cumsum(y_sorted * ~t_sorted)
    ratio = np.divide(
        cum_treated,
        cum_control,
        out=np.zeros(n, dtype=float),
        where=cum_control > 0,
    )
    incremental = cum_treated_y - cum_control_y * ratio
    incremental = np.where((cum_treated > 0) & (cum_control > 0), incremental, np.nan)
    incremental = np.concatenate([[0.0], incremental])

    fractions = np.linspace(0.0, 1.0, n_points)
    cutoffs = np.clip(np.ceil(fractions * n).astype(int), 0, n)
    model_curve = np.nan_to_num(incremental[cutoffs], nan=0.0) / n
    random_curve = fractions * total_incremental / n

    auuc = float(np.trapezoid(model_curve, fractions))
    random_auuc = float(total_incremental / n * 0.5)
    qini = (auuc - random_auuc) / random_auuc if abs(random_auuc) > 1e-12 else None

    top_decile_n = max(1, math.ceil(0.1 * n))
    top_decile_incremental = float(incremental[top_decile_n])
    top_decile_uplift = top_decile_incremental / top_decile_n
    top_decile_share = (
        top_decile_incremental / total_incremental if abs(total_incremental) > 1e-12 else None
    )

    points = tuple(
        CurvePoint(
            fraction=float(fraction),
            model=float(model),
            random=float(random),
        )
        for fraction, model, random in zip(fractions, model_curve, random_curve, strict=True)
    )
    metrics = UpliftMetrics(
        total_incremental=float(total_incremental),
        overall_uplift=float(total_incremental / n),
        auuc=auuc,
        random_auuc=random_auuc,
        qini=None if qini is None else float(qini),
        uplift_top_decile=float(top_decile_uplift),
        top_decile_share=None if top_decile_share is None else float(top_decile_share),
    )
    return metrics, points


def segment_rows(
    y: np.ndarray,
    treatment: np.ndarray,
    score: np.ndarray,
    *,
    n_segments: int = 5,
) -> tuple[SegmentRow, ...]:
    """Split the holdout by score rank and compare predicted and observed uplift."""
    y = np.asarray(y, dtype=float)
    treatment = np.asarray(treatment, dtype=np.int8)
    score = np.asarray(score, dtype=float)
    n = y.size
    if n_segments < 2:
        raise AnalysisError("need at least two segments")

    order = np.argsort(score, kind="stable")
    assignment = np.empty(n, dtype=np.int64)
    assignment[order] = np.minimum(np.arange(n) * n_segments // n, n_segments - 1)

    rows: list[SegmentRow] = []
    for index in range(n_segments):
        mask = assignment == index
        observed: float | None = None
        ci_low: float | None = None
        ci_high: float | None = None
        try:
            result = difference_in_means(y[mask], treatment[mask])
            observed = result.estimate
            ci_low = result.ci_low
            ci_high = result.ci_high
        except AnalysisError:
            pass
        rows.append(
            SegmentRow(
                segment=index + 1,
                label=f"Q{index + 1}",
                n=int(mask.sum()),
                treated_share=float((treatment[mask] == 1).mean()),
                predicted_uplift=float(score[mask].mean()),
                observed_uplift=observed,
                ci_low=ci_low,
                ci_high=ci_high,
            )
        )
    return tuple(rows)


def _top_indices(score: np.ndarray, fraction: float) -> np.ndarray:
    if not 0.0 < fraction <= 1.0:
        raise AnalysisError("budget fraction must be in (0, 1]")
    n = score.size
    k = max(1, min(n, math.ceil(fraction * n)))
    return np.argsort(-score, kind="stable")[:k]


def _bootstrap_profit(
    y: np.ndarray,
    treatment: np.ndarray,
    n_target: int,
    value_per_conversion: float,
    cost_per_contact: float,
    *,
    n_bootstrap: int,
    seed: int,
) -> tuple[float | None, float | None]:
    treated_y = y[treatment == 1]
    control_y = y[treatment == 0]
    if treated_y.size < 2 or control_y.size < 2 or n_bootstrap <= 0:
        return None, None
    rng = np.random.default_rng(seed)
    profits = np.empty(n_bootstrap, dtype=float)
    for index in range(n_bootstrap):
        resampled_treated = rng.choice(treated_y, size=treated_y.size, replace=True)
        resampled_control = rng.choice(control_y, size=control_y.size, replace=True)
        incremental = resampled_treated.sum() - resampled_control.sum() * (
            treated_y.size / control_y.size
        )
        profits[index] = incremental * value_per_conversion - n_target * cost_per_contact
    low, high = np.percentile(profits, [2.5, 97.5])
    return float(low), float(high)


def policy_value(
    name: str,
    y: np.ndarray,
    treatment: np.ndarray,
    score: np.ndarray,
    *,
    budget_fraction: float,
    value_per_conversion: float,
    cost_per_contact: float,
    n_bootstrap: int = 0,
    seed: int = 42,
) -> PolicyResult:
    """Profit for targeting the top score fraction, using observed holdout outcomes."""
    if not math.isfinite(value_per_conversion) or value_per_conversion < 0:
        raise AnalysisError("value per conversion must be finite and non-negative")
    if not math.isfinite(cost_per_contact) or cost_per_contact < 0:
        raise AnalysisError("cost per contact must be finite and non-negative")

    y = np.asarray(y, dtype=float)
    treatment = np.asarray(treatment, dtype=np.int8)
    score = np.asarray(score, dtype=float)
    indices = _top_indices(score, budget_fraction)
    selected_y = y[indices]
    selected_t = treatment[indices]
    incremental = _total_incremental(selected_y, selected_t)
    value = incremental * value_per_conversion
    cost = indices.size * cost_per_contact
    profit = value - cost
    ci_low, ci_high = _bootstrap_profit(
        selected_y,
        selected_t,
        indices.size,
        value_per_conversion,
        cost_per_contact,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    return PolicyResult(
        name=name,
        budget_fraction=float(budget_fraction),
        n_target=int(indices.size),
        incremental_conversions=float(incremental),
        value=float(value),
        cost=float(cost),
        profit=float(profit),
        roi=float(profit / cost) if cost > 0 else None,
        ci_low=ci_low,
        ci_high=ci_high,
        n_bootstrap=n_bootstrap,
    )


def random_policy(
    y: np.ndarray,
    treatment: np.ndarray,
    *,
    budget_fraction: float,
    value_per_conversion: float,
    cost_per_contact: float,
) -> PolicyResult:
    """Expected profit from targeting an unranked random fraction."""
    total = _total_incremental(y, treatment)
    n_target = max(1, min(y.size, math.ceil(budget_fraction * y.size)))
    incremental = total * (n_target / y.size)
    value = incremental * value_per_conversion
    cost = n_target * cost_per_contact
    profit = value - cost
    return PolicyResult(
        name="random",
        budget_fraction=float(budget_fraction),
        n_target=n_target,
        incremental_conversions=float(incremental),
        value=float(value),
        cost=float(cost),
        profit=float(profit),
        roi=float(profit / cost) if cost > 0 else None,
        ci_low=None,
        ci_high=None,
        n_bootstrap=0,
    )


def treat_all_policy(
    y: np.ndarray,
    treatment: np.ndarray,
    *,
    value_per_conversion: float,
    cost_per_contact: float,
) -> PolicyResult:
    incremental = _total_incremental(y, treatment)
    value = incremental * value_per_conversion
    cost = y.size * cost_per_contact
    profit = value - cost
    return PolicyResult(
        name="treat_all",
        budget_fraction=1.0,
        n_target=int(y.size),
        incremental_conversions=float(incremental),
        value=float(value),
        cost=float(cost),
        profit=float(profit),
        roi=float(profit / cost) if cost > 0 else None,
        ci_low=None,
        ci_high=None,
        n_bootstrap=0,
    )


def baseline_policies(
    y: np.ndarray,
    treatment: np.ndarray,
    *,
    budget_fraction: float,
    value_per_conversion: float,
    cost_per_contact: float,
) -> tuple[PolicyResult, ...]:
    """Treat-all and random baselines for the same budget and unit economics."""
    return (
        treat_all_policy(
            y,
            treatment,
            value_per_conversion=value_per_conversion,
            cost_per_contact=cost_per_contact,
        ),
        random_policy(
            y,
            treatment,
            budget_fraction=budget_fraction,
            value_per_conversion=value_per_conversion,
            cost_per_contact=cost_per_contact,
        ),
    )


def profit_curve(
    y: np.ndarray,
    treatment: np.ndarray,
    score: np.ndarray,
    *,
    value_per_conversion: float,
    cost_per_contact: float,
    n_points: int = 20,
) -> tuple[PolicyResult, ...]:
    """Price the model policy across the full budget range without bootstrap."""
    if n_points < 2:
        raise AnalysisError("profit curve needs at least two points")
    fractions = np.linspace(1.0 / n_points, 1.0, n_points)
    return tuple(
        policy_value(
            f"budget_{fraction:.2f}",
            y,
            treatment,
            score,
            budget_fraction=float(fraction),
            value_per_conversion=value_per_conversion,
            cost_per_contact=cost_per_contact,
        )
        for fraction in fractions
    )


def metrics_with_baselines(
    metrics: UpliftMetrics,
    baselines: Sequence[PolicyResult],
) -> dict[str, object]:
    """Small helper for report renderers that need a named policy lookup."""
    return {
        "metrics": metrics.to_dict(),
        "baselines": {policy.name: policy.to_dict() for policy in baselines},
    }
