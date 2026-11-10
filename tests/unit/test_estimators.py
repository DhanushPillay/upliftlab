"""Hand-checked ATE and bootstrap behavior."""

from __future__ import annotations

import numpy as np
import pytest

from upliftlab.errors import AnalysisError
from upliftlab.experiment.estimators import bootstrap_difference_in_means, difference_in_means


def test_welch_ate_hand_computed() -> None:
    y = np.array([1.0, 2.0, 3.0, 4.0])
    treatment = np.array([0, 0, 1, 1], dtype=np.int8)
    result = difference_in_means(y, treatment)
    assert result.estimate == pytest.approx(2.0)
    assert result.standard_error == pytest.approx(np.sqrt(0.5))
    assert result.p_value == pytest.approx(0.1055728, rel=1e-6)
    assert result.ci_low == pytest.approx(-1.043, abs=1e-3)
    assert result.ci_high == pytest.approx(5.043, abs=1e-3)
    assert result.n_treated == 2
    assert result.n_control == 2


def test_bootstrap_is_seeded_and_ordered() -> None:
    rng = np.random.default_rng(3)
    y = rng.normal(size=500)
    treatment = rng.integers(0, 2, size=500, dtype=np.int8)
    first = bootstrap_difference_in_means(y, treatment, n_bootstrap=300, seed=11)
    second = bootstrap_difference_in_means(y, treatment, n_bootstrap=300, seed=11)
    assert first == second
    assert first.ci_low < first.estimate < first.ci_high


def test_bootstrap_rejects_too_few_draws() -> None:
    with pytest.raises(AnalysisError):
        bootstrap_difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.array([0, 0, 1, 1], dtype=np.int8),
            n_bootstrap=50,
        )


def test_zero_variance_raises() -> None:
    with pytest.raises(AnalysisError):
        difference_in_means(
            np.array([1.0, 1.0, 1.0, 1.0]),
            np.array([0, 0, 1, 1], dtype=np.int8),
        )


def test_treatment_must_be_binary() -> None:
    with pytest.raises(AnalysisError):
        difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.array([0, 0, 1, 2], dtype=np.int8),
        )


def test_treatment_rejects_fractional_values_instead_of_truncating() -> None:
    with pytest.raises(AnalysisError, match="binary"):
        difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.array([0.0, 0.5, 1.0, 1.5]),
        )


def test_treatment_rejects_non_numeric_values() -> None:
    with pytest.raises(AnalysisError, match="numeric"):
        difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.array(["0", "0", "1", "1"]),
        )


def test_treatment_rejects_non_finite_values() -> None:
    with pytest.raises(AnalysisError, match="non-finite"):
        difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.array([0.0, 0.0, 1.0, np.nan]),
        )


def test_treatment_rejects_two_dimensional_input() -> None:
    with pytest.raises(AnalysisError, match="one-dimensional"):
        difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.zeros((4, 2), dtype=np.int8),
        )


def test_outcome_rejects_infinite_values() -> None:
    with pytest.raises(AnalysisError, match="non-finite"):
        difference_in_means(
            np.array([0.0, 1.0, np.inf, 3.0]),
            np.array([0, 0, 1, 1], dtype=np.int8),
        )


def test_outcome_and_treatment_must_match_length() -> None:
    with pytest.raises(AnalysisError, match="same length"):
        difference_in_means(
            np.array([0.0, 1.0, 2.0]),
            np.array([0, 0, 1, 1], dtype=np.int8),
        )


def test_each_arm_needs_two_observations() -> None:
    with pytest.raises(AnalysisError, match="two observations"):
        difference_in_means(
            np.array([0.0, 1.0, 2.0, 3.0]),
            np.array([0, 0, 0, 1], dtype=np.int8),
        )
