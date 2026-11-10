"""Properties that must hold for any valid input."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from upliftlab.experiment.estimators import difference_in_means


@given(
    values=st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=40,
    ),
    shift=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_ate_is_invariant_to_constant_shift(values: list[float], shift: float) -> None:
    y = np.asarray(values, dtype=float)
    treatment = np.array([0] * (len(y) // 2) + [1] * (len(y) - len(y) // 2), dtype=np.int8)
    assume(np.var(y[treatment == 0], ddof=1) > 0.0)
    assume(np.var(y[treatment == 1], ddof=1) > 0.0)

    original = difference_in_means(y, treatment)
    shifted = difference_in_means(y + shift, treatment)
    assert shifted.estimate == pytest.approx(original.estimate, abs=1e-9)
    assert shifted.ci_low == pytest.approx(original.ci_low, abs=1e-9)
    assert shifted.ci_high == pytest.approx(original.ci_high, abs=1e-9)
