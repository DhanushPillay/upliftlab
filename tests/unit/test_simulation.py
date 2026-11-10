"""Synthetic calibration tests with a small replication count."""

from __future__ import annotations

import numpy as np

from upliftlab.simulation import SCENARIOS, get_scenario, render_simulation, run_scenario
from upliftlab.simulation.runner import run_simulation
from upliftlab.simulation.scenarios import draw_experiment


def test_draw_experiment_is_seeded_and_binary() -> None:
    scenario = get_scenario("constant")
    first = draw_experiment(scenario, np.random.default_rng(7))
    second = draw_experiment(scenario, np.random.default_rng(7))
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])
    assert set(np.unique(first[0])) <= {0, 1}
    assert set(np.unique(first[1])) <= {0, 1}
    assert first[0].shape == (scenario.n,)


def test_constant_scenario_is_calibrated() -> None:
    result = run_scenario(get_scenario("constant"), replications=300, seed=11)
    assert result.true_ate == 0.03
    assert abs(result.bias) < 0.01
    assert 0.85 <= result.coverage <= 1.0
    assert abs(result.mean_estimate - 0.03) < 0.01


def test_simulation_report_round_trips() -> None:
    report = run_simulation(replications=100, seed=3, scenarios=SCENARIOS[:2])
    payload = report.to_dict()
    assert payload["schema_version"] == 1
    assert len(payload["scenarios"]) == 2
    assert payload["scenarios"][0]["replications"] == 100
    text = render_simulation(report)
    assert "Simulation benchmark" in text
    assert "null" in text
