"""Markdown rendering for the uplift and policy report."""

from __future__ import annotations

import math

from upliftlab.uplift.types import PolicyResult, UpliftReport


def _number(value: float | None, digits: int = 4) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _percent(value: float | None, digits: int = 1) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def _money(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:,.2f}"


def _dict_float(data: dict[str, object], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _policy_row(policy: PolicyResult) -> str:
    interval = (
        f"[{_money(policy.ci_low)}, {_money(policy.ci_high)}]"
        if policy.ci_low is not None and policy.ci_high is not None
        else "n/a"
    )
    return (
        f"| {policy.name} | {_percent(policy.budget_fraction, 0)} | "
        f"{policy.n_target:,} | {_number(policy.incremental_conversions, 1)} | "
        f"{_money(policy.value)} | {_money(policy.cost)} | {_money(policy.profit)} | "
        f"{_percent(policy.roi)} | {interval} |"
    )


def render_uplift(report: UpliftReport) -> str:
    """Render a compact report. All numbers come from the typed result."""
    budget_label = (
        f"${report.budget_dollars:,.0f}"
        if report.budget_dollars is not None
        else _percent(report.policy.budget_fraction, 0)
    )
    lines: list[str] = [
        f"# Uplift and policy report: {report.dataset}",
        "",
        f"Outcome `{report.outcome}`. Intent-to-treat. The holdout was not used to fit "
        "or select the model.",
        "",
        "## Summary",
        "",
        f"- Model: {report.model_name}",
        f"- Selected candidate: {report.selected_candidate}",
        f"- Seed: {report.seed}",
        f"- Split: {report.split['train']:,} train, {report.split['validation']:,} validation, "
        f"{report.split['holdout']:,} holdout",
        f"- Holdout ATE: {_number(_dict_float(report.holdout_ate, 'estimate'))} "
        f"(95% CI {_number(_dict_float(report.holdout_ate, 'ci_low'))} to "
        f"{_number(_dict_float(report.holdout_ate, 'ci_high'))})",
        f"- Qini coefficient: {_number(report.metrics.qini, 3)}",
        f"- AUUC: {_number(report.metrics.auuc, 4)}",
        f"- Uplift in the top decile: {_number(report.metrics.uplift_top_decile, 4)}",
        f"- Policy budget: {budget_label}",
        f"- Policy profit at {budget_label} budget: {_money(report.policy.profit)}",
        "",
        "## Policy value",
        "",
        "| Policy | Budget | Customers | Incremental | Value | Cost | Profit | ROI | "
        "95% bootstrap CI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _policy_row(report.policy),
        *(_policy_row(baseline) for baseline in report.baselines),
        "",
        "The model policy targets the highest predicted uplift first. Treat-all and random "
        "are evaluated on the same holdout. The interval resamples outcomes within the "
        "selected customers, so it does not include model-selection uncertainty.",
        "",
        "## Profit versus budget",
        "",
        "| Budget | Customers | Incremental | Value | Cost | Profit | ROI |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *(
            f"| {_percent(point.budget_fraction, 0)} | {point.n_target:,} | "
            f"{_number(point.incremental_conversions, 1)} | {_money(point.value)} | "
            f"{_money(point.cost)} | {_money(point.profit)} | {_percent(point.roi)} |"
            for point in report.profit_curve
        ),
        "",
        "The curve re-prices the same holdout ranking at each budget. It is descriptive: "
        "the points are correlated, and no point is a causal estimate for a future campaign.",
        "",
        "## Observed uplift by predicted rank",
        "",
        "| Segment | Customers | Treated share | Predicted uplift | Observed uplift | 95% CI |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.segments:
        interval = (
            f"[{_number(row.ci_low)}, {_number(row.ci_high)}]"
            if row.ci_low is not None and row.ci_high is not None
            else "n/a"
        )
        lines.append(
            f"| {row.label} | {row.n:,} | {_percent(row.treated_share, 0)} | "
            f"{_number(row.predicted_uplift)} | {_number(row.observed_uplift)} | "
            f"{interval} |"
        )
    lines.extend(
        [
            "",
            "Segments are rank buckets by predicted uplift, not causal strata. A flat "
            "observed curve means the model did not separate persuadable customers.",
            "",
            "## Caveats",
            "",
            *(f"- {caveat}" for caveat in report.caveats),
            "",
            "Qini and AUUC measure ranking quality. Policy profit uses observed holdout "
            "outcomes and the stated value and cost assumptions. Neither is a guarantee "
            "for a future campaign.",
            "",
        ]
    )
    return "\n".join(lines)
