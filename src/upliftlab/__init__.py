"""upliftlab: experiment readout and uplift targeting.

Public API is intentionally small. Everything not listed in ``__all__`` is
internal during 0.x and may change.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from upliftlab.config import AnalysisConfig
from upliftlab.datasets import fetch_dataset, load_dataset
from upliftlab.experiment import (
    analyze_experiment,
    bootstrap_difference_in_means,
    compute_balance,
    cuped_ate,
    difference_in_means,
    srm_test,
)
from upliftlab.report import render_readout
from upliftlab.results import ReadoutResult

try:
    __version__ = version("upliftlab")
except PackageNotFoundError:  # pragma: no cover - source tree without install
    __version__ = "0.0.0.dev0"

__all__ = [
    "AnalysisConfig",
    "ReadoutResult",
    "__version__",
    "analyze_experiment",
    "bootstrap_difference_in_means",
    "compute_balance",
    "cuped_ate",
    "difference_in_means",
    "fetch_dataset",
    "load_dataset",
    "render_readout",
    "srm_test",
]
