"""Dataset contracts shared by loaders and analysis code."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from upliftlab.errors import SchemaError


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    name: str
    url: str
    sha256: str
    filename: str
    rows: int
    columns: tuple[str, ...]
    arm_column: str
    treatment_column: str
    outcome_columns: tuple[str, ...]
    srm_labels: tuple[str, ...]
    srm_expected: tuple[float, ...]
    balance_covariates: tuple[str, ...]
    categorical_covariates: tuple[str, ...]
    citation: str
    license_note: str


@dataclass(frozen=True, slots=True)
class Dataset:
    name: str
    frame: pd.DataFrame
    spec: DatasetSpec


def validate_schema(frame: pd.DataFrame, spec: DatasetSpec) -> None:
    """Require the exact declared columns and row count."""
    actual = set(frame.columns)
    expected = set(spec.columns)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        parts: list[str] = []
        if missing:
            parts.append(f"missing columns: {', '.join(missing)}")
        if unexpected:
            parts.append(f"unexpected columns: {', '.join(unexpected)}")
        raise SchemaError(f"{spec.name}: {'; '.join(parts)}")
    if len(frame) != spec.rows:
        raise SchemaError(f"{spec.name}: expected {spec.rows} rows, got {len(frame)}")
