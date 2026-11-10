"""Synthetic experiments with a known average treatment effect."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    description: str
    p_control: float
    effect: float
    effect_slope: float = 0.0
    treatment_share: float = 0.5
    n: int = 10_000

    @property
    def true_ate(self) -> float:
        # x is Uniform(0, 1), so the slope contributes half its value on average.
        return self.effect + 0.5 * self.effect_slope


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="null",
        description="No effect; checks Type I error.",
        p_control=0.10,
        effect=0.0,
    ),
    Scenario(
        name="constant",
        description="Constant +3 percentage point effect.",
        p_control=0.10,
        effect=0.03,
    ),
    Scenario(
        name="heterogeneous",
        description="Effect rises with a pre-treatment score; average +2 points.",
        p_control=0.10,
        effect=0.0,
        effect_slope=0.04,
    ),
    Scenario(
        name="harmful",
        description="Constant -2 percentage point effect.",
        p_control=0.12,
        effect=-0.02,
    ),
    Scenario(
        name="unbalanced",
        description="20/80 allocation with a +2 point effect.",
        p_control=0.10,
        effect=0.02,
        treatment_share=0.2,
    ),
)


def get_scenario(name: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    raise KeyError(name)


def draw_experiment(
    scenario: Scenario,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Return binary outcomes and treatment assignments for one experiment."""
    treatment = rng.binomial(1, scenario.treatment_share, size=scenario.n).astype(np.int8)
    score = rng.uniform(0.0, 1.0, size=scenario.n)
    control_probability = np.full(scenario.n, scenario.p_control, dtype=float)
    treated_probability = scenario.p_control + scenario.effect + scenario.effect_slope * score
    probability = np.where(treatment == 1, treated_probability, control_probability)
    outcome = rng.binomial(1, np.clip(probability, 0.0, 1.0)).astype(np.int8)
    return outcome, treatment
