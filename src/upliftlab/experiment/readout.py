"""Compose validation, estimation, and CUPED into one readout."""

from __future__ import annotations

import numpy as np

from upliftlab.config import AnalysisConfig
from upliftlab.datasets.base import Dataset
from upliftlab.errors import AnalysisError
from upliftlab.experiment.cuped import cuped_ate
from upliftlab.experiment.estimators import (
    bootstrap_difference_in_means,
    coerce_binary_treatment,
    difference_in_means,
)
from upliftlab.experiment.validation import compute_balance, srm_test
from upliftlab.results import ReadoutResult


def analyze_experiment(
    dataset: Dataset,
    config: AnalysisConfig | None = None,
) -> ReadoutResult:
    """Run the pre-registered readout for a binary treatment and binary outcome."""
    config = config or AnalysisConfig()
    frame = dataset.frame
    spec = dataset.spec

    for column in (config.outcome, config.covariate, spec.arm_column, spec.treatment_column):
        if column not in frame.columns:
            raise AnalysisError(f"{dataset.name}: missing column {column}")

    if config.outcome not in spec.outcome_columns:
        raise AnalysisError(
            f"{dataset.name}: outcome {config.outcome!r} is not declared for this dataset"
        )
    if config.covariate not in spec.balance_covariates:
        raise AnalysisError(
            f"{dataset.name}: covariate {config.covariate!r} is not a pre-treatment covariate"
        )
    if config.covariate in spec.outcome_columns or config.covariate in (
        spec.arm_column,
        spec.treatment_column,
    ):
        raise AnalysisError(
            f"{dataset.name}: covariate {config.covariate!r} is an outcome or treatment column"
        )

    present = set(frame[spec.arm_column].dropna().unique())
    unexpected_arms = sorted(present - set(spec.srm_labels))
    if unexpected_arms:
        raise AnalysisError(f"{dataset.name}: unexpected SRM arms: {unexpected_arms}")
    missing_arms = [label for label in spec.srm_labels if label not in present]
    if missing_arms:
        raise AnalysisError(f"{dataset.name}: missing SRM arms: {missing_arms}")

    counts = frame[spec.arm_column].value_counts().reindex(spec.srm_labels).fillna(0).astype(int)
    if int(counts.sum()) != len(frame):
        raise AnalysisError(f"{dataset.name}: arm counts do not cover every row")
    srm = srm_test(
        counts.tolist(),
        labels=spec.srm_labels,
        expected=spec.srm_expected,
        alpha=0.001,
    )

    treatment = coerce_binary_treatment(frame[spec.treatment_column].to_numpy())
    try:
        outcome = frame[config.outcome].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"{dataset.name}: outcome {config.outcome!r} must be numeric") from exc
    if not np.isfinite(outcome).all():
        raise AnalysisError(f"{dataset.name}: outcome {config.outcome!r} has non-finite values")

    balance = compute_balance(
        frame,
        spec.treatment_column,
        spec.balance_covariates,
        categorical=spec.categorical_covariates,
    )
    ate = difference_in_means(outcome, treatment, alpha=config.alpha)
    bootstrap = bootstrap_difference_in_means(
        outcome,
        treatment,
        n_bootstrap=config.bootstrap,
        seed=config.seed,
        alpha=config.alpha,
    )
    cuped = cuped_ate(
        frame,
        spec.treatment_column,
        config.outcome,
        config.covariate,
        alpha=config.alpha,
    )

    return ReadoutResult(
        dataset=dataset.name,
        dataset_sha256=spec.sha256,
        rows=len(frame),
        outcome=config.outcome,
        covariate=config.covariate,
        alpha=config.alpha,
        seed=config.seed,
        bootstrap=config.bootstrap,
        srm=srm,
        balance=balance,
        ate=ate,
        bootstrap_result=bootstrap,
        cuped=cuped,
        caveats=(
            "Estimates are intention-to-treat: assignment is the treatment, not open or click.",
            (
                f"The primary outcome is {config.outcome}. Other declared outcomes are "
                "not tested in this report."
            ),
            (
                "The treated arm is a 1:1 mixture of Mens E-Mail and Womens E-Mail; the "
                "estimate is the effect of assignment to that mixture."
            ),
            (
                "CUPED theta is fit on the analysed sample; for a holdout, fit theta on "
                "training data only. The variance reduction is descriptive."
            ),
            "Balance is descriptive. No significance test is applied to covariate means.",
            "This report tests one outcome, so no multiple-testing correction is applied.",
        ),
    )
