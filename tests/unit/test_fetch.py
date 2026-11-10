"""Download behavior with a fake HTTP response, no network."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
import requests

from upliftlab.datasets import fetch as fetch_module
from upliftlab.datasets.base import DatasetSpec
from upliftlab.datasets.fetch import download_dataset
from upliftlab.errors import ChecksumError, DataError


def _spec(payload: bytes, *, filename: str = "data.bin") -> DatasetSpec:
    return DatasetSpec(
        name="test",
        url="https://example.com/data.bin",
        sha256=hashlib.sha256(payload).hexdigest(),
        filename=filename,
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


class _Response:
    def __init__(
        self,
        payload: bytes,
        *,
        content_length: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        self.error = error

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    def iter_content(self, chunk_size: int) -> object:
        for start in range(0, len(self.payload), chunk_size):
            yield self.payload[start : start + chunk_size]


def test_download_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"hello upliftlab"
    monkeypatch.setattr(
        fetch_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(payload, content_length=len(payload)),
    )
    path = download_dataset(_spec(payload), tmp_path)
    assert path.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


def test_download_checksum_mismatch_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"hello"
    spec = _spec(payload)
    bad = replace(spec, sha256="0" * 64)
    monkeypatch.setattr(
        fetch_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(payload, content_length=len(payload)),
    )
    with pytest.raises(ChecksumError):
        download_dataset(bad, tmp_path)
    assert not (tmp_path / spec.filename).exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_rejects_declared_size_over_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"hello"
    monkeypatch.setattr(
        fetch_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(
            payload, content_length=fetch_module.MAX_DOWNLOAD_BYTES + 1
        ),
    )
    with pytest.raises(DataError, match="declared download"):
        download_dataset(_spec(payload), tmp_path)


def test_download_rejects_stream_over_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"hello"
    monkeypatch.setattr(fetch_module, "MAX_DOWNLOAD_BYTES", 4)
    monkeypatch.setattr(
        fetch_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(payload),
    )
    with pytest.raises(DataError, match="download exceeds"):
        download_dataset(_spec(payload), tmp_path)


def test_download_wraps_request_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"hello"
    monkeypatch.setattr(
        fetch_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(payload, error=requests.RequestException("boom")),
    )
    with pytest.raises(DataError, match="download failed"):
        download_dataset(_spec(payload), tmp_path)
