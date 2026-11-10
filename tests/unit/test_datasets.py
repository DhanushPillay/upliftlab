"""Loader, schema, and checksum tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from upliftlab.datasets import get_spec, load_dataset
from upliftlab.datasets.base import DatasetSpec, validate_schema
from upliftlab.datasets.fetch import download_dataset, sha256_file, verify_checksum
from upliftlab.datasets.hillstrom import HILLSTROM, load_hillstrom
from upliftlab.errors import ChecksumError, DataError, SchemaError


def test_load_hillstrom_adds_treatment(hillstrom_gz_path: Path) -> None:
    dataset = load_hillstrom(hillstrom_gz_path)
    assert len(dataset.frame) == 64_000
    assert dataset.frame["treatment"].isin([0, 1]).all()
    assert not dataset.frame["treatment"].isna().any()
    assert dataset.frame["treatment"].sum() > 0


def test_load_hillstrom_pins_treatment_direction(hillstrom_gz_path: Path) -> None:
    frame = load_hillstrom(hillstrom_gz_path).frame
    mapping = frame.groupby("segment", observed=True)["treatment"].unique()
    assert mapping["No E-Mail"].tolist() == [0]
    assert mapping["Mens E-Mail"].tolist() == [1]
    assert mapping["Womens E-Mail"].tolist() == [1]


def test_load_dataset_rejects_corrupt_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / HILLSTROM.filename).write_bytes(b"not the pinned file")

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("corrupt cache must not trigger a download")

    monkeypatch.setattr("upliftlab.datasets.fetch.requests.get", _fail)
    with pytest.raises(ChecksumError, match="expected sha256"):
        load_dataset("hillstrom", tmp_path)


def test_load_hillstrom_rejects_missing_column(hillstrom_gz_path: Path, tmp_path: Path) -> None:
    frame = pd.read_csv(hillstrom_gz_path)
    broken = tmp_path / "broken.csv"
    frame.drop(columns=["segment"]).to_csv(broken, index=False)
    with pytest.raises(SchemaError, match="missing columns"):
        load_hillstrom(broken)


def test_verify_checksum_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "bytes.bin"
    path.write_bytes(b"upliftlab")
    expected = hashlib.sha256(b"upliftlab").hexdigest()
    assert sha256_file(path) == expected
    verify_checksum(path, expected)
    with pytest.raises(ChecksumError):
        verify_checksum(path, "0" * 64)


def test_download_rejects_plain_http(tmp_path: Path) -> None:
    spec = DatasetSpec(
        name="test",
        url="http://example.com/data.csv",
        sha256="0" * 64,
        filename="data.csv",
        rows=1,
        columns=("x",),
        arm_column="x",
        treatment_column="x",
        outcome_columns=("x",),
        srm_labels=("a", "b"),
        srm_expected=(0.5, 0.5),
        balance_covariates=("x",),
        categorical_covariates=(),
        citation="none",
        license_note="none",
    )
    with pytest.raises(DataError, match="HTTPS"):
        download_dataset(spec, tmp_path)


def test_cached_file_is_verified(tmp_path: Path) -> None:
    path = tmp_path / "cached.bin"
    path.write_bytes(b"cached")
    spec = DatasetSpec(
        name="test",
        url="https://example.com/cached.bin",
        sha256=hashlib.sha256(b"cached").hexdigest(),
        filename="cached.bin",
        rows=1,
        columns=("x",),
        arm_column="x",
        treatment_column="x",
        outcome_columns=("x",),
        srm_labels=("a", "b"),
        srm_expected=(0.5, 0.5),
        balance_covariates=("x",),
        categorical_covariates=(),
        citation="none",
        license_note="none",
    )
    assert download_dataset(spec, tmp_path) == path


def test_registry_rejects_unknown_dataset() -> None:
    with pytest.raises(DataError, match="unknown dataset"):
        get_spec("nope")


def test_load_dataset_requires_a_fetch(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="upliftlab fetch hillstrom"):
        load_dataset("hillstrom", tmp_path)


def test_schema_rejects_wrong_row_count(hillstrom_frame: pd.DataFrame) -> None:
    with pytest.raises(SchemaError, match="expected 64000 rows"):
        validate_schema(hillstrom_frame.head(10), HILLSTROM)


def test_schema_rejects_unexpected_column(hillstrom_frame: pd.DataFrame) -> None:
    with pytest.raises(SchemaError, match="unexpected columns"):
        validate_schema(hillstrom_frame.assign(extra=1), HILLSTROM)


def test_loader_rejects_unknown_segment(hillstrom_frame: pd.DataFrame, tmp_path: Path) -> None:
    frame = hillstrom_frame.copy()
    frame.loc[0, "segment"] = "Unknown"
    path = tmp_path / "unknown.csv.gz"
    frame.to_csv(path, index=False, compression="gzip")
    with pytest.raises(SchemaError, match="unknown segment"):
        load_hillstrom(path)


def test_loader_rejects_non_binary_outcome(hillstrom_frame: pd.DataFrame, tmp_path: Path) -> None:
    frame = hillstrom_frame.copy()
    frame.loc[0, "visit"] = 2
    path = tmp_path / "bad-visit.csv.gz"
    frame.to_csv(path, index=False, compression="gzip")
    with pytest.raises(SchemaError, match="visit must be binary"):
        load_hillstrom(path)


def test_loader_rejects_negative_spend(hillstrom_frame: pd.DataFrame, tmp_path: Path) -> None:
    frame = hillstrom_frame.copy()
    frame.loc[0, "spend"] = -1.0
    path = tmp_path / "bad-spend.csv.gz"
    frame.to_csv(path, index=False, compression="gzip")
    with pytest.raises(SchemaError, match="spend must be non-negative"):
        load_hillstrom(path)
