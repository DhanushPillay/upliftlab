"""Uplift ranking, policy arithmetic, and report contracts."""

from __future__ import annotations

import numpy as np
import pytest

from upliftlab.datasets.base import Dataset
from upliftlab.datasets.hillstrom import HILLSTROM
from upliftlab.errors import ConfigError
from upliftlab.uplift import (
    UpliftConfig,
    build_report,
    fit_uplift,
    policy_for_budget,
    qini_metrics,
    render_uplift,
    target_rows,
)
from upliftlab.uplift.evaluation import policy_value, profit_curve


def test_qini_rewards_a_real_ranking_signal() -> None:
    rng = np.random.default_rng(11)
    n = 6_000
    score = rng.uniform(size=n)
    treatment = rng.integers(0, 2, size=n, dtype=np.int8)
    probability = np.where(treatment == 1, 0.08 + 0.18 * score, 0.08)
    outcome = rng.binomial(1, probability).astype(np.int8)

    metrics, curve = qini_metrics(outcome, treatment, score)

    assert metrics.qini is not None
    assert metrics.qini > 0.1
    assert metrics.uplift_top_decile > metrics.overall_uplift
    assert len(curve) == 101
    assert curve[0].fraction == 0.0
    assert curve[-1].fraction == 1.0


def test_policy_value_uses_the_targeted_subset() -> None:
    outcome = np.array([1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    treatment = np.array([1, 1, 0, 0, 1, 0, 1, 0], dtype=np.int8)
    score = np.array([4.0, 3.0, 2.5, 2.0, 1.0, 0.5, 0.0, 0.0])

    policy = policy_value(
        "model",
        outcome,
        treatment,
        score,
        budget_fraction=0.5,
        value_per_conversion=10.0,
        cost_per_contact=1.0,
    )

    assert policy.n_target == 4
    assert policy.incremental_conversions == pytest.approx(2.0)
    assert policy.value == pytest.approx(20.0)
    assert policy.cost == pytest.approx(4.0)
    assert policy.profit == pytest.approx(16.0)
    assert policy.roi == pytest.approx(4.0)


def test_uplift_config_rejects_impossible_splits() -> None:
    with pytest.raises(ConfigError):
        UpliftConfig(validation_fraction=0.5, holdout_fraction=0.6)
    with pytest.raises(ConfigError):
        UpliftConfig(budget_fraction=0.0)


@pytest.fixture(scope="module")
def small_dataset(hillstrom_dataset: Dataset) -> Dataset:
    frame = hillstrom_dataset.frame.iloc[:12_000].copy()
    return Dataset(name="hillstrom", frame=frame, spec=HILLSTROM)


@pytest.fixture(scope="module")
def fitted(small_dataset: Dataset):  # type: ignore[no-untyped-def]
    config = UpliftConfig(
        outcome="visit",
        seed=5,
        max_iter=30,
        min_samples_leaf=20,
        policy_bootstrap=20,
    )
    return fit_uplift(small_dataset, config), config


def test_fit_uplift_produces_a_holdout_report(fitted) -> None:  # type: ignore[no-untyped-def]
    model, config = fitted
    report = build_report(model, config)

    assert sum(report.split.values()) == 12_000
    assert report.model_name == "T-learner (HistGradientBoostingClassifier)"
    assert len(report.segments) == 5
    assert report.policy.n_bootstrap == 20
    assert len(report.baselines) == 2
    assert report.caveats


def test_render_uplift_has_the_policy_and_calibration_sections(fitted) -> None:  # type: ignore[no-untyped-def]
    model, config = fitted
    report = build_report(model, config)
    markdown = render_uplift(report)

    assert "# Uplift and policy report: hillstrom" in markdown
    assert "## Policy value" in markdown
    assert "## Observed uplift by predicted rank" in markdown
    assert "Q5" in markdown
    assert "Policy value uses observed holdout outcomes" in "\n".join(report.caveats)


def test_policy_for_budget_reprices_without_refitting(fitted) -> None:  # type: ignore[no-untyped-def]
    model, config = fitted
    policy, baselines = policy_for_budget(model, config, 0.1)

    assert policy.budget_fraction == pytest.approx(0.1)
    assert policy.n_target == 240
    assert len(baselines) == 2


def test_dollar_budget_resolves_to_the_cost_based_count(fitted) -> None:  # type: ignore[no-untyped-def]
    model, config = fitted
    dollar_config = UpliftConfig(
        outcome=config.outcome,
        seed=config.seed,
        budget_dollars=6.0,
        value_per_conversion=config.value_per_conversion,
        cost_per_contact=0.05,
        policy_bootstrap=0,
    )

    report = build_report(model, dollar_config)

    assert report.policy.n_target == 120
    assert report.budget_dollars == pytest.approx(6.0)
    assert report.policy.budget_fraction == pytest.approx(0.05)
    assert len(report.profit_curve) == 20
    assert report.profit_curve[-1].budget_fraction == pytest.approx(1.0)


def test_report_serializes_the_profit_curve_and_dollar_budget(fitted) -> None:  # type: ignore[no-untyped-def]
    model, config = fitted
    dollar_config = UpliftConfig(
        outcome=config.outcome,
        seed=config.seed,
        budget_dollars=6.0,
        cost_per_contact=0.05,
        policy_bootstrap=0,
    )

    payload = build_report(model, dollar_config).to_dict()

    assert payload["budget_dollars"] == pytest.approx(6.0)
    assert len(payload["profit_curve"]) == 20  # type: ignore[arg-type]
    assert payload["profit_curve"][0]["budget_fraction"] == pytest.approx(0.05)  # type: ignore[index]
    assert payload["schema_version"] == 3


def test_profit_curve_covers_the_budget_range() -> None:
    n = 200
    order = np.arange(n)
    y = ((order % 3) == 0).astype(float)
    treatment = (order % 2).astype(np.int8)
    score = np.arange(n, dtype=float)

    curve = profit_curve(y, treatment, score, value_per_conversion=10.0, cost_per_contact=1.0)

    assert len(curve) == 20
    assert curve[0].budget_fraction == pytest.approx(0.05)
    assert curve[-1].budget_fraction == pytest.approx(1.0)
    assert curve[-1].n_target == y.size


def test_target_rows_are_ranked_and_use_original_indices(fitted) -> None:  # type: ignore[no-untyped-def]
    model, config = fitted
    rows = target_rows(model, config)

    assert len(rows) == model.split["holdout"] * 0.2
    assert [row["rank"] for row in rows] == list(range(1, len(rows) + 1))
    scores = [float(row["predicted_uplift"]) for row in rows]
    assert scores == sorted(scores, reverse=True)
    holdout_rows = {int(value) for value in model.holdout_index}
    assert all(int(row["row"]) in holdout_rows for row in rows)
