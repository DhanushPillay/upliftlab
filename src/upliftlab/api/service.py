"""Application services. Cache the fitted model, not the rendered response."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from upliftlab.config import AnalysisConfig
from upliftlab.datasets import ensure_dataset
from upliftlab.datasets.base import Dataset
from upliftlab.experiment import analyze_experiment
from upliftlab.uplift.model import (
    FittedUplift,
    UpliftConfig,
    build_report,
    fit_uplift,
    policy_for_budget,
)

DATA_DIR = Path(os.environ.get("UPLIFTLAB_DATA_DIR", "data/raw"))


@lru_cache(maxsize=2)
def _dataset(name: str, data_dir_text: str) -> Dataset:
    return ensure_dataset(name, Path(data_dir_text))


@lru_cache(maxsize=8)
def _fitted(name: str, outcome: str, seed: int, data_dir_text: str) -> FittedUplift:
    dataset = _dataset(name, data_dir_text)
    config = UpliftConfig(outcome=outcome, seed=seed)
    return fit_uplift(dataset, config)


def overview(
    *,
    dataset: str,
    outcome: str,
    seed: int,
    alpha: float,
    bootstrap: int,
    budget_fraction: float,
    value_per_conversion: float,
    cost_per_contact: float,
    policy_bootstrap: int,
) -> dict[str, Any]:
    data = _dataset(dataset, str(DATA_DIR))
    readout = analyze_experiment(
        data,
        AnalysisConfig(
            outcome=outcome,
            covariate="history",
            alpha=alpha,
            bootstrap=bootstrap,
            seed=seed,
        ),
    )

    fitted = _fitted(dataset, outcome, seed, str(DATA_DIR))
    config = UpliftConfig(
        outcome=outcome,
        seed=seed,
        budget_fraction=budget_fraction,
        value_per_conversion=value_per_conversion,
        cost_per_contact=cost_per_contact,
        policy_bootstrap=policy_bootstrap,
    )
    report = build_report(fitted, config)
    return {
        "dataset": data.name,
        "rows": len(data.frame),
        "sha256": data.spec.sha256,
        "readout": readout.to_dict(),
        "uplift": report.to_dict(),
    }


def policy(
    *,
    dataset: str,
    outcome: str,
    seed: int,
    budget_fraction: float,
    value_per_conversion: float,
    cost_per_contact: float,
    policy_bootstrap: int,
) -> dict[str, Any]:
    fitted = _fitted(dataset, outcome, seed, str(DATA_DIR))
    config = UpliftConfig(
        outcome=outcome,
        seed=seed,
        budget_fraction=budget_fraction,
        value_per_conversion=value_per_conversion,
        cost_per_contact=cost_per_contact,
        policy_bootstrap=policy_bootstrap,
    )
    chosen, baselines = policy_for_budget(fitted, config, budget_fraction)
    return {
        "policy": chosen.to_dict(),
        "baselines": [baseline.to_dict() for baseline in baselines],
    }
