"""Hillstrom MineThatData email dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from upliftlab.datasets.base import Dataset, DatasetSpec, validate_schema
from upliftlab.errors import SchemaError

_TREATMENT = {
    "No E-Mail": 0,
    "Mens E-Mail": 1,
    "Womens E-Mail": 1,
}

HILLSTROM = DatasetSpec(
    name="hillstrom",
    url="https://hillstorm1.s3.us-east-2.amazonaws.com/hillstorm_no_indices.csv.gz",
    sha256="bab6578f60db5d792f1c2372c502f029152a5249cf5ea84390f3b7f885d7234f",
    filename="hillstorm_no_indices.csv.gz",
    rows=64_000,
    columns=(
        "recency",
        "history_segment",
        "history",
        "mens",
        "womens",
        "zip_code",
        "newbie",
        "channel",
        "segment",
        "visit",
        "conversion",
        "spend",
    ),
    arm_column="segment",
    treatment_column="treatment",
    outcome_columns=("visit", "conversion", "spend"),
    srm_labels=tuple(_TREATMENT),
    srm_expected=(1 / 3, 1 / 3, 1 / 3),
    balance_covariates=(
        "recency",
        "history",
        "mens",
        "womens",
        "newbie",
        "history_segment",
        "zip_code",
        "channel",
    ),
    categorical_covariates=("history_segment", "zip_code", "channel"),
    citation=(
        "Hillstrom, K. (2008). MineThatData E-Mail Analytics And Data Mining "
        "Challenge. https://blog.minethatdata.com/2008/03/"
        "minethatdata-e-mail-analytics-and-data.html"
    ),
    license_note=(
        "No formal license is stated. Cite the source. Do not redistribute the "
        "raw file or row-level derivatives."
    ),
)

_DTYPES: dict[str, str] = {
    "recency": "int64",
    "history": "float64",
    "mens": "int8",
    "womens": "int8",
    "newbie": "int8",
    "visit": "int8",
    "conversion": "int8",
    "spend": "float64",
    "history_segment": "string",
    "zip_code": "string",
    "channel": "string",
    "segment": "string",
}


def load_hillstrom(path: Path) -> Dataset:
    try:
        frame = pd.read_csv(path, dtype=_DTYPES, compression="infer")
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise SchemaError(f"hillstrom: cannot parse {path}: {exc}") from exc
    validate_schema(frame, HILLSTROM)

    unknown = set(frame["segment"].dropna().unique()) - set(_TREATMENT)
    if unknown:
        raise SchemaError(f"hillstrom: unknown segment values: {sorted(unknown)}")
    if frame["segment"].isna().any():
        raise SchemaError("hillstrom: segment contains missing values")

    treatment = frame["segment"].map(_TREATMENT)
    if treatment.isna().any():
        raise SchemaError("hillstrom: could not map segment to treatment")
    frame = frame.assign(treatment=treatment.astype("int8"))

    for column in ("visit", "conversion"):
        if not frame[column].isin([0, 1]).all():
            raise SchemaError(f"hillstrom: {column} must be binary")
    if (frame["spend"] < 0).any():
        raise SchemaError("hillstrom: spend must be non-negative")

    return Dataset(name="hillstrom", frame=frame, spec=HILLSTROM)
