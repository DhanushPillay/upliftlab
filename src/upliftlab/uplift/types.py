"""Typed Phase 2 uplift results.

The report keeps scores, metrics, and policy assumptions separate so a good
ranking cannot be mistaken for a profitable decision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def _clean(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value


@dataclass(frozen=True, slots=True)
class CurvePoint:
    fraction: float
    model: float
    random: float

    def to_dict(self) -> dict[str, float]:
        return {
            "fraction": self.fraction,
            "model": self.model,
            "random": self.random,
        }


@dataclass(frozen=True, slots=True)
class UpliftMetrics:
    total_incremental: float
    overall_uplift: float
    auuc: float
    random_auuc: float
    qini: float | None
    uplift_top_decile: float
    top_decile_share: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "total_incremental": _clean(self.total_incremental),
            "overall_uplift": _clean(self.overall_uplift),
            "auuc": _clean(self.auuc),
            "random_auuc": _clean(self.random_auuc),
            "qini": _clean(self.qini),
            "uplift_top_decile": _clean(self.uplift_top_decile),
            "top_decile_share": _clean(self.top_decile_share),
        }


@dataclass(frozen=True, slots=True)
class SegmentRow:
    segment: int
    label: str
    n: int
    treated_share: float
    predicted_uplift: float
    observed_uplift: float | None
    ci_low: float | None
    ci_high: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "segment": self.segment,
            "label": self.label,
            "n": self.n,
            "treated_share": self.treated_share,
            "predicted_uplift": self.predicted_uplift,
            "observed_uplift": _clean(self.observed_uplift),
            "ci_low": _clean(self.ci_low),
            "ci_high": _clean(self.ci_high),
        }


@dataclass(frozen=True, slots=True)
class PolicyResult:
    name: str
    budget_fraction: float
    n_target: int
    incremental_conversions: float
    value: float
    cost: float
    profit: float
    roi: float | None
    ci_low: float | None
    ci_high: float | None
    n_bootstrap: int

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "budget_fraction": self.budget_fraction,
            "n_target": self.n_target,
            "incremental_conversions": _clean(self.incremental_conversions),
            "value": _clean(self.value),
            "cost": _clean(self.cost),
            "profit": _clean(self.profit),
            "roi": _clean(self.roi),
            "ci_low": _clean(self.ci_low),
            "ci_high": _clean(self.ci_high),
            "n_bootstrap": self.n_bootstrap,
        }


@dataclass(frozen=True, slots=True)
class UpliftReport:
    dataset: str
    dataset_sha256: str
    outcome: str
    seed: int
    model_name: str
    selected_candidate: str
    split: dict[str, int]
    holdout_ate: dict[str, object]
    metrics: UpliftMetrics
    curve: tuple[CurvePoint, ...]
    segments: tuple[SegmentRow, ...]
    policy: PolicyResult
    baselines: tuple[PolicyResult, ...]
    profit_curve: tuple[PolicyResult, ...]
    budget_dollars: float | None
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 3,
            "dataset": self.dataset,
            "dataset_sha256": self.dataset_sha256,
            "outcome": self.outcome,
            "seed": self.seed,
            "model_name": self.model_name,
            "selected_candidate": self.selected_candidate,
            "split": self.split,
            "holdout_ate": self.holdout_ate,
            "metrics": self.metrics.to_dict(),
            "curve": [point.to_dict() for point in self.curve],
            "segments": [row.to_dict() for row in self.segments],
            "policy": self.policy.to_dict(),
            "baselines": [baseline.to_dict() for baseline in self.baselines],
            "profit_curve": [point.to_dict() for point in self.profit_curve],
            "budget_dollars": _clean(self.budget_dollars),
            "caveats": list(self.caveats),
        }
