"""Readout composition and report rendering."""

from __future__ import annotations

import numpy as np
import pytest

from upliftlab.config import AnalysisConfig
from upliftlab.datasets.base import Dataset
from upliftlab.errors import AnalysisError
from upliftlab.experiment.readout import analyze_experiment
from upliftlab.report.markdown import render_readout


def test_readout_contains_expected_sections(hillstrom_dataset: Dataset) -> None:
    result = analyze_experiment(hillstrom_dataset, AnalysisConfig(bootstrap=200))
    assert result.rows == 64_000
    assert result.srm.labels == ("No E-Mail", "Mens E-Mail", "Womens E-Mail")
    assert result.ate.n_treated + result.ate.n_control == 64_000
    assert result.cuped.correlation > 0.0

    report = render_readout(result)
    assert "# Experiment readout: hillstrom" in report
    assert "## Summary" in report
    assert "## Sample ratio" in report
    assert "## Covariate balance" in report
    assert "## Caveats" in report
    assert "CUPED adjusted" in report


def test_readout_treatment_direction_gives_positive_effect(hillstrom_dataset: Dataset) -> None:
    """The fixture makes e-mail lift visit, so the sign pins the 0/1 coding."""
    result = analyze_experiment(hillstrom_dataset, AnalysisConfig(bootstrap=100))
    assert result.ate.estimate > 0.0
    assert result.ate.ci_low > 0.0


def test_report_uses_configured_alpha_and_outcome(hillstrom_dataset: Dataset) -> None:
    config = AnalysisConfig(outcome="conversion", alpha=0.1, bootstrap=100)
    report = render_readout(analyze_experiment(hillstrom_dataset, config))
    assert "90% CI" in report
    assert "95% CI" not in report
    assert "Primary outcome: `conversion`" in report
    assert "did the email change the `conversion` rate" in report


def test_readout_records_the_dataset_hash(hillstrom_dataset: Dataset) -> None:
    result = analyze_experiment(hillstrom_dataset, AnalysisConfig(bootstrap=100))
    assert result.dataset_sha256 == hillstrom_dataset.spec.sha256
    assert result.to_dict()["dataset_sha256"] == hillstrom_dataset.spec.sha256


def test_readout_rejects_post_treatment_covariate(hillstrom_dataset: Dataset) -> None:
    config = AnalysisConfig(covariate="visit", bootstrap=100)
    with pytest.raises(AnalysisError, match="not a pre-treatment covariate"):
        analyze_experiment(hillstrom_dataset, config)


def test_readout_rejects_undeclared_outcome(hillstrom_dataset: Dataset) -> None:
    config = AnalysisConfig(outcome="history", bootstrap=100)
    with pytest.raises(AnalysisError, match="not declared"):
        analyze_experiment(hillstrom_dataset, config)


def test_readout_rejects_unexpected_arm(hillstrom_dataset: Dataset) -> None:
    frame = hillstrom_dataset.frame.copy()
    frame.loc[frame.index[0], "segment"] = "Carrier Pigeon"
    dataset = Dataset(name=hillstrom_dataset.name, frame=frame, spec=hillstrom_dataset.spec)
    with pytest.raises(AnalysisError, match="unexpected SRM arms"):
        analyze_experiment(dataset, AnalysisConfig(bootstrap=100))


def test_readout_rejects_missing_arm(hillstrom_dataset: Dataset) -> None:
    frame = hillstrom_dataset.frame
    frame = frame[frame["segment"] != "Womens E-Mail"]
    dataset = Dataset(name=hillstrom_dataset.name, frame=frame, spec=hillstrom_dataset.spec)
    with pytest.raises(AnalysisError, match="missing SRM arms"):
        analyze_experiment(dataset, AnalysisConfig(bootstrap=100))


def test_readout_rejects_non_numeric_outcome(hillstrom_dataset: Dataset) -> None:
    frame = hillstrom_dataset.frame.copy()
    frame["visit"] = np.where(frame["visit"] == 1, "yes", "no")
    dataset = Dataset(name=hillstrom_dataset.name, frame=frame, spec=hillstrom_dataset.spec)
    with pytest.raises(AnalysisError, match="must be numeric"):
        analyze_experiment(dataset, AnalysisConfig(bootstrap=100))


def test_readout_rejects_non_finite_outcome(hillstrom_dataset: Dataset) -> None:
    frame = hillstrom_dataset.frame.copy()
    frame["visit"] = frame["visit"].astype(float)
    frame.loc[frame.index[0], "visit"] = float("inf")
    dataset = Dataset(name=hillstrom_dataset.name, frame=frame, spec=hillstrom_dataset.spec)
    with pytest.raises(AnalysisError, match="non-finite"):
        analyze_experiment(dataset, AnalysisConfig(bootstrap=100))
