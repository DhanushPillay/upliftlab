"""CUPED behavior on a known linear covariate."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from upliftlab.errors import AnalysisError
from upliftlab.experiment.cuped import cuped_ate


def test_cuped_recovers_theta_and_reduces_variance() -> None:
    rng = np.random.default_rng(7)
    n = 20_000
    x = rng.normal(size=n)
    treatment = rng.integers(0, 2, size=n, dtype=np.int8)
    y = 2.0 * x + rng.normal(scale=0.5, size=n) + 0.1 * treatment
    frame = pd.DataFrame({"treatment": treatment, "y": y, "x": x})

    result = cuped_ate(frame, "treatment", "y", "x")

    assert result.theta == pytest.approx(2.0, abs=0.05)
    assert result.variance_reduction > 0.8
    assert result.adjusted.estimate == pytest.approx(result.raw.estimate, abs=0.1)


def test_cuped_rejects_constant_covariate() -> None:
    frame = pd.DataFrame(
        {
            "treatment": [0, 0, 1, 1],
            "y": [0.0, 1.0, 2.0, 3.0],
            "x": [1.0, 1.0, 1.0, 1.0],
        }
    )
    with pytest.raises(AnalysisError):
        cuped_ate(frame, "treatment", "y", "x")


def test_cuped_variance_reduction_is_squared_correlation() -> None:
    rng = np.random.default_rng(11)
    n = 5_000
    x = rng.normal(size=n)
    treatment = rng.integers(0, 2, size=n, dtype=np.int8)
    y = -1.5 * x + rng.normal(scale=1.0, size=n) + 0.2 * treatment
    frame = pd.DataFrame({"treatment": treatment, "y": y, "x": x})

    result = cuped_ate(frame, "treatment", "y", "x")

    theta = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    adjusted = y - theta * (x - x.mean())
    expected_raw = y[treatment == 1].mean() - y[treatment == 0].mean()
    expected_adjusted = adjusted[treatment == 1].mean() - adjusted[treatment == 0].mean()
    assert result.theta == pytest.approx(theta, rel=1e-12)
    assert result.raw.estimate == pytest.approx(expected_raw, rel=1e-12)
    assert result.adjusted.estimate == pytest.approx(expected_adjusted, rel=1e-12)
    assert result.variance_reduction == pytest.approx(result.correlation**2, rel=1e-12)


def test_cuped_uses_a_supplied_theta() -> None:
    rng = np.random.default_rng(5)
    n = 1_000
    x = rng.normal(size=n)
    treatment = rng.integers(0, 2, size=n, dtype=np.int8)
    y = 3.0 * x + rng.normal(scale=1.0, size=n) + 0.1 * treatment
    frame = pd.DataFrame({"treatment": treatment, "y": y, "x": x})

    result = cuped_ate(frame, "treatment", "y", "x", theta=3.0)

    assert result.theta == pytest.approx(3.0)


def test_cuped_rejects_non_finite_covariate() -> None:
    frame = pd.DataFrame(
        {"treatment": [0, 0, 1, 1], "y": [0.0, 1.0, 2.0, 3.0], "x": [0.0, 1.0, np.inf, 3.0]}
    )
    with pytest.raises(AnalysisError, match="non-finite"):
        cuped_ate(frame, "treatment", "y", "x")


def test_cuped_rejects_non_numeric_columns() -> None:
    frame = pd.DataFrame(
        {"treatment": [0, 0, 1, 1], "y": [0.0, 1.0, 2.0, 3.0], "x": ["a", "b", "c", "d"]}
    )
    with pytest.raises(AnalysisError, match="numeric"):
        cuped_ate(frame, "treatment", "y", "x")


def test_cuped_rejects_non_finite_theta() -> None:
    frame = pd.DataFrame(
        {"treatment": [0, 0, 1, 1], "y": [0.0, 1.0, 2.0, 3.0], "x": [0.0, 1.0, 2.0, 3.0]}
    )
    with pytest.raises(AnalysisError, match="theta"):
        cuped_ate(frame, "treatment", "y", "x", theta=float("nan"))
