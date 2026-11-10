"""T-learner uplift model with validation-based candidate selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
from sklearn.model_selection import train_test_split  # type: ignore[import-untyped]
from sklearn.preprocessing import OneHotEncoder  # type: ignore[import-untyped]

from upliftlab.datasets.base import Dataset
from upliftlab.errors import AnalysisError, ConfigError
from upliftlab.experiment.estimators import difference_in_means
from upliftlab.uplift.evaluation import (
    baseline_policies,
    policy_value,
    qini_metrics,
    segment_rows,
)
from upliftlab.uplift.types import (
    CurvePoint,
    PolicyResult,
    SegmentRow,
    UpliftMetrics,
    UpliftReport,
)


@dataclass(frozen=True, slots=True)
class Candidate:
    label: str
    learning_rate: float
    max_leaf_nodes: int
    l2_regularization: float


_CANDIDATES: tuple[Candidate, ...] = (
    Candidate("leaves=15, lr=0.06", 0.06, 15, 1.0),
    Candidate("leaves=31, lr=0.08", 0.08, 31, 1.0),
)


@dataclass(frozen=True, slots=True)
class UpliftConfig:
    outcome: str = "visit"
    seed: int = 42
    validation_fraction: float = 0.2
    holdout_fraction: float = 0.2
    max_iter: int = 200
    min_samples_leaf: int = 40
    budget_fraction: float = 0.2
    value_per_conversion: float = 2.0
    cost_per_contact: float = 0.05
    policy_bootstrap: int = 200

    def __post_init__(self) -> None:
        if not self.outcome:
            raise ConfigError("outcome must be a non-empty string")
        if self.seed < 0:
            raise ConfigError("seed must be non-negative")
        if not 0.0 < self.validation_fraction < 1.0:
            raise ConfigError("validation_fraction must be strictly between 0 and 1")
        if not 0.0 < self.holdout_fraction < 1.0:
            raise ConfigError("holdout_fraction must be strictly between 0 and 1")
        if self.validation_fraction + self.holdout_fraction >= 1.0:
            raise ConfigError("validation and holdout fractions must sum to less than 1")
        if self.max_iter < 10:
            raise ConfigError("max_iter must be at least 10")
        if self.min_samples_leaf < 1:
            raise ConfigError("min_samples_leaf must be positive")
        if not 0.0 < self.budget_fraction <= 1.0:
            raise ConfigError("budget_fraction must be in (0, 1]")
        if self.value_per_conversion < 0.0:
            raise ConfigError("value_per_conversion must be non-negative")
        if self.cost_per_contact < 0.0:
            raise ConfigError("cost_per_contact must be non-negative")
        if self.policy_bootstrap < 0:
            raise ConfigError("policy_bootstrap must be non-negative")


@dataclass(slots=True)
class FittedUplift:
    dataset: str
    dataset_sha256: str
    outcome: str
    seed: int
    model_name: str
    selected_candidate: str
    split: dict[str, int]
    metrics: UpliftMetrics
    curve: tuple[CurvePoint, ...]
    segments: tuple[SegmentRow, ...]
    holdout_y: np.ndarray
    holdout_treatment: np.ndarray
    holdout_score: np.ndarray


def _validate_frame(dataset: Dataset, config: UpliftConfig) -> tuple[np.ndarray, np.ndarray]:
    frame = dataset.frame
    spec = dataset.spec
    for column in (config.outcome, spec.treatment_column):
        if column not in frame.columns:
            raise AnalysisError(f"{dataset.name}: missing column {column}")
    if config.outcome not in spec.outcome_columns:
        raise AnalysisError(
            f"{dataset.name}: outcome {config.outcome!r} is not declared for this dataset"
        )
    try:
        y = frame[config.outcome].to_numpy(dtype=np.int8)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"{dataset.name}: outcome must be binary") from exc
    treatment = frame[spec.treatment_column].to_numpy(dtype=np.int8)
    if not np.isin(y, [0, 1]).all():
        raise AnalysisError(f"{dataset.name}: {config.outcome} must be binary")
    if not np.isin(treatment, [0, 1]).all():
        raise AnalysisError(f"{dataset.name}: {spec.treatment_column} must be binary")
    if len(frame) < 100:
        raise AnalysisError(f"{dataset.name}: need at least 100 rows to fit an uplift model")
    return y, treatment


def _split_indices(
    y: np.ndarray,
    treatment: np.ndarray,
    config: UpliftConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(y)
    strata = pd.Series(treatment.astype(str) + "_" + y.astype(str))
    test_size = config.validation_fraction + config.holdout_fraction
    train_idx, rest_idx = train_test_split(
        np.arange(n),
        test_size=test_size,
        stratify=strata,
        random_state=config.seed,
    )
    validation_idx, holdout_idx = train_test_split(
        rest_idx,
        test_size=0.5,
        stratify=strata.iloc[rest_idx],
        random_state=config.seed + 1,
    )
    for name, index in (
        ("train", train_idx),
        ("validation", validation_idx),
        ("holdout", holdout_idx),
    ):
        if len(np.unique(treatment[index])) < 2:
            raise AnalysisError(f"{name} split does not contain both treatment arms")
    return np.sort(train_idx), np.sort(validation_idx), np.sort(holdout_idx)


def _feature_columns(dataset: Dataset) -> tuple[list[str], list[str]]:
    spec = dataset.spec
    features = list(spec.balance_covariates)
    missing = [column for column in features if column not in dataset.frame.columns]
    if missing:
        raise AnalysisError(f"{dataset.name}: missing uplift features: {missing}")
    categorical = [column for column in spec.categorical_covariates if column in features]
    numeric = [column for column in features if column not in categorical]
    return numeric, categorical


def _design_frame(
    frame: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
) -> pd.DataFrame:
    design = frame[numeric + categorical].copy()
    for column in numeric:
        try:
            design[column] = pd.to_numeric(design[column], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise AnalysisError(f"uplift feature {column!r} must be numeric") from exc
        if not np.isfinite(design[column].to_numpy()).all():
            raise AnalysisError(f"uplift feature {column!r} contains non-finite values")
    for column in categorical:
        design[column] = design[column].astype(str)
    return design


def _preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", numeric),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float64),
                categorical,
            ),
        ],
        remainder="drop",
    )


def _fit_pair(
    x_train: np.ndarray,
    y_train: np.ndarray,
    treatment_train: np.ndarray,
    candidate: Candidate,
    config: UpliftConfig,
) -> tuple[HistGradientBoostingClassifier, HistGradientBoostingClassifier]:
    common: dict[str, Any] = {
        "learning_rate": candidate.learning_rate,
        "max_leaf_nodes": candidate.max_leaf_nodes,
        "l2_regularization": candidate.l2_regularization,
        "min_samples_leaf": config.min_samples_leaf,
        "max_iter": config.max_iter,
        "early_stopping": False,
        "random_state": config.seed,
    }
    control = HistGradientBoostingClassifier(**common)
    treated = HistGradientBoostingClassifier(**common)
    control.fit(x_train[treatment_train == 0], y_train[treatment_train == 0])
    treated.fit(x_train[treatment_train == 1], y_train[treatment_train == 1])
    return control, treated


def _score_pair(
    control: HistGradientBoostingClassifier,
    treated: HistGradientBoostingClassifier,
    x: np.ndarray,
) -> np.ndarray:
    score = treated.predict_proba(x)[:, 1] - control.predict_proba(x)[:, 1]
    return np.asarray(score, dtype=float)


def fit_uplift(dataset: Dataset, config: UpliftConfig | None = None) -> FittedUplift:
    """Fit a T-learner, select a candidate on validation AUUC, evaluate on holdout."""
    config = config or UpliftConfig()
    frame = dataset.frame
    spec = dataset.spec
    y, treatment = _validate_frame(dataset, config)
    train_idx, validation_idx, holdout_idx = _split_indices(y, treatment, config)

    numeric, categorical = _feature_columns(dataset)
    design = _design_frame(frame, numeric, categorical)
    encoder = _preprocessor(numeric, categorical)
    x_train = encoder.fit_transform(design.iloc[train_idx])
    x_validation = encoder.transform(design.iloc[validation_idx])
    x_holdout = encoder.transform(design.iloc[holdout_idx])

    best: (
        tuple[
            float,
            Candidate,
            HistGradientBoostingClassifier,
            HistGradientBoostingClassifier,
        ]
        | None
    ) = None
    for candidate in _CANDIDATES:
        control, treated = _fit_pair(x_train, y[train_idx], treatment[train_idx], candidate, config)
        score = _score_pair(control, treated, x_validation)
        metrics, _ = qini_metrics(y[validation_idx], treatment[validation_idx], score)
        gain = metrics.auuc - metrics.random_auuc
        if best is None or gain > best[0]:
            best = (gain, candidate, control, treated)
    if best is None:
        raise AnalysisError("no uplift candidate could be fitted")
    _, candidate, _, _ = best

    fit_idx = np.concatenate([train_idx, validation_idx])
    x_fit = encoder.transform(design.iloc[fit_idx])
    control, treated = _fit_pair(x_fit, y[fit_idx], treatment[fit_idx], candidate, config)
    score = _score_pair(control, treated, x_holdout)
    metrics, curve = qini_metrics(y[holdout_idx], treatment[holdout_idx], score)
    segments = segment_rows(y[holdout_idx], treatment[holdout_idx], score)

    return FittedUplift(
        dataset=dataset.name,
        dataset_sha256=spec.sha256,
        outcome=config.outcome,
        seed=config.seed,
        model_name="T-learner (HistGradientBoostingClassifier)",
        selected_candidate=candidate.label,
        split={
            "train": len(train_idx),
            "validation": len(validation_idx),
            "holdout": len(holdout_idx),
        },
        metrics=metrics,
        curve=curve,
        segments=segments,
        holdout_y=y[holdout_idx],
        holdout_treatment=treatment[holdout_idx],
        holdout_score=score,
    )


def build_report(fitted: FittedUplift, config: UpliftConfig | None = None) -> UpliftReport:
    """Attach a budget policy and baselines to a fitted holdout evaluation."""
    config = config or UpliftConfig()
    holdout_ate = difference_in_means(fitted.holdout_y, fitted.holdout_treatment)
    policy = policy_value(
        "uplift model",
        fitted.holdout_y,
        fitted.holdout_treatment,
        fitted.holdout_score,
        budget_fraction=config.budget_fraction,
        value_per_conversion=config.value_per_conversion,
        cost_per_contact=config.cost_per_contact,
        n_bootstrap=config.policy_bootstrap,
        seed=config.seed,
    )
    baselines = baseline_policies(
        fitted.holdout_y,
        fitted.holdout_treatment,
        budget_fraction=config.budget_fraction,
        value_per_conversion=config.value_per_conversion,
        cost_per_contact=config.cost_per_contact,
    )
    return UpliftReport(
        dataset=fitted.dataset,
        dataset_sha256=fitted.dataset_sha256,
        outcome=fitted.outcome,
        seed=fitted.seed,
        model_name=fitted.model_name,
        selected_candidate=fitted.selected_candidate,
        split=fitted.split,
        holdout_ate=holdout_ate.to_dict(),
        metrics=fitted.metrics,
        curve=fitted.curve,
        segments=fitted.segments,
        policy=policy,
        baselines=baselines,
        caveats=(
            "Scores are differences between two outcome models, not guaranteed individual effects.",
            "Candidate selection used validation AUUC; the holdout was not used to "
            "choose the model.",
            "Policy value uses observed holdout outcomes for the selected customers.",
            "Bootstrap intervals resample outcomes within arm and condition on the "
            "selected customers.",
            "Hillstrom treatment is assignment to any e-mail; effects are intention-to-treat.",
            "Criteo and multi-budget optimization are not included in this Phase 2 slice.",
        ),
    )


def run_uplift(dataset: Dataset, config: UpliftConfig | None = None) -> UpliftReport:
    """Fit, select, evaluate, and price one uplift policy."""
    config = config or UpliftConfig()
    return build_report(fit_uplift(dataset, config), config)


def policy_for_budget(
    fitted: FittedUplift,
    config: UpliftConfig,
    budget_fraction: float,
) -> tuple[PolicyResult, tuple[PolicyResult, ...]]:
    """Re-price an already fitted holdout at a new budget."""
    policy = policy_value(
        "uplift model",
        fitted.holdout_y,
        fitted.holdout_treatment,
        fitted.holdout_score,
        budget_fraction=budget_fraction,
        value_per_conversion=config.value_per_conversion,
        cost_per_contact=config.cost_per_contact,
        n_bootstrap=config.policy_bootstrap,
        seed=config.seed,
    )
    baselines = baseline_policies(
        fitted.holdout_y,
        fitted.holdout_treatment,
        budget_fraction=budget_fraction,
        value_per_conversion=config.value_per_conversion,
        cost_per_contact=config.cost_per_contact,
    )
    return policy, baselines
