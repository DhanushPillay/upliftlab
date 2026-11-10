"""Hand-checked validation behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from upliftlab.errors import AnalysisError
from upliftlab.experiment.validation import compute_balance, srm_test


def test_srm_equal_counts_are_not_flagged() -> None:
    result = srm_test([100, 100, 100])
    assert result.detected is False
    assert result.p_value == pytest.approx(1.0)
    assert result.method == "chi-square"


def test_srm_detects_large_imbalance() -> None:
    result = srm_test([200, 100, 100], alpha=0.001)
    assert result.detected is True
    assert result.p_value < 0.001


def test_srm_rejects_zero_total() -> None:
    with pytest.raises(AnalysisError):
        srm_test([0, 0, 0])


def test_srm_rejects_bad_expected_proportions() -> None:
    with pytest.raises(AnalysisError):
        srm_test([10, 10], expected=[0.5, 0.6])


def test_balance_is_zero_for_identical_arms() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1], "x": [1.0, 1.0, 1.0, 1.0]})
    rows = compute_balance(frame, "treatment", ["x"])
    assert len(rows) == 1
    assert rows[0].smd == pytest.approx(0.0)
    assert rows[0].treated_mean == pytest.approx(1.0)


def test_balance_sign_flips_when_arms_swap() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1], "x": [0.0, 0.5, 1.0, 1.5]})
    forward = compute_balance(frame, "treatment", ["x"])[0]
    swapped = frame.assign(treatment=1 - frame["treatment"])
    backward = compute_balance(swapped, "treatment", ["x"])[0]
    assert forward.smd > 0
    assert backward.smd == pytest.approx(-forward.smd)


def test_balance_categorical_dummies() -> None:
    frame = pd.DataFrame(
        {
            "treatment": [0, 0, 1, 1],
            "channel": ["Phone", "Web", "Phone", "Web"],
        }
    )
    rows = compute_balance(frame, "treatment", ["channel"], categorical=["channel"])
    names = {row.covariate for row in rows}
    assert names == {"channel_Phone", "channel_Web"}
    assert all(np.isfinite(row.smd) for row in rows)


def test_srm_rejects_bad_alpha() -> None:
    with pytest.raises(AnalysisError):
        srm_test([10, 10], alpha=1.5)


def test_srm_rejects_label_length() -> None:
    with pytest.raises(AnalysisError):
        srm_test([10, 10], labels=["only-one"])


def test_srm_rejects_expected_shape() -> None:
    with pytest.raises(AnalysisError):
        srm_test([10, 10], expected=[0.5, 0.5, 0.0])


def test_srm_rejects_zero_expected_proportion() -> None:
    with pytest.raises(AnalysisError):
        srm_test([10, 10], expected=[0.0, 1.0])


def test_srm_uses_binomial_fallback_for_small_arms() -> None:
    result = srm_test([2, 1])
    assert result.method == "binomial"
    assert np.isnan(result.chi_square)


def test_balance_rejects_missing_treatment() -> None:
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(AnalysisError, match="missing treatment"):
        compute_balance(frame, "treatment", ["x"])


def test_balance_rejects_non_binary_treatment() -> None:
    frame = pd.DataFrame({"treatment": [0, 1, 2, 0], "x": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(AnalysisError, match="binary"):
        compute_balance(frame, "treatment", ["x"])


def test_balance_rejects_missing_covariate() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1]})
    with pytest.raises(AnalysisError, match="missing balance covariate"):
        compute_balance(frame, "treatment", ["x"])


def test_balance_rejects_missing_values() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1], "x": [1.0, np.nan, 2.0, 3.0]})
    with pytest.raises(AnalysisError, match="missing values"):
        compute_balance(frame, "treatment", ["x"])


def test_balance_reports_infinite_smd_when_pooled_variance_is_zero() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1], "x": [0.0, 0.0, 1.0, 1.0]})
    row = compute_balance(frame, "treatment", ["x"])[0]
    assert np.isinf(row.smd)


def test_balance_needs_two_observations_per_arm() -> None:
    frame = pd.DataFrame({"treatment": [0, 1, 1, 1], "x": [0.0, 1.0, 2.0, 3.0]})
    with pytest.raises(AnalysisError, match="two observations"):
        compute_balance(frame, "treatment", ["x"])


def test_srm_rejects_fractional_counts() -> None:
    with pytest.raises(AnalysisError, match="integers"):
        srm_test([10.5, 10.0])


def test_srm_rejects_non_finite_counts() -> None:
    with pytest.raises(AnalysisError, match="finite"):
        srm_test([np.inf, 10])


def test_srm_rejects_two_dimensional_counts() -> None:
    with pytest.raises(AnalysisError, match="at least two arms"):
        srm_test(np.array([[10, 10]]))


def test_srm_rejects_non_numeric_counts() -> None:
    with pytest.raises(AnalysisError, match="numeric"):
        srm_test(["ten", "ten"])  # type: ignore[list-item]


def test_srm_rejects_non_finite_expected() -> None:
    with pytest.raises(AnalysisError, match="finite"):
        srm_test([10, 10], expected=[np.nan, 1.0])


def test_balance_rejects_non_numeric_covariate() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1], "x": ["a", "b", "c", "d"]})
    with pytest.raises(AnalysisError, match="must be numeric"):
        compute_balance(frame, "treatment", ["x"])


def test_balance_rejects_non_finite_covariate() -> None:
    frame = pd.DataFrame({"treatment": [0, 0, 1, 1], "x": [0.0, 1.0, np.inf, 3.0]})
    with pytest.raises(AnalysisError, match="non-finite"):
        compute_balance(frame, "treatment", ["x"])
