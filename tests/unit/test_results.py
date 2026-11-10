"""Canonical JSON and atomic text output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from upliftlab.errors import ReportError
from upliftlab.results import write_json, write_text


def test_write_json_sorts_keys_and_newline(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    write_json({"b": 1, "a": 2}, path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')
    assert json.loads(text) == {"a": 2, "b": 1}


def test_write_json_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    write_json({"a": 2}, path)
    with pytest.raises(ReportError, match="--force"):
        write_json({"a": 3}, path)
    write_json({"a": 3}, path, overwrite=True)
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 3}


def test_write_json_rejects_nan(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    with pytest.raises(ReportError, match="non-finite"):
        write_json({"x": float("nan")}, path)
    assert not path.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_write_text_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    write_text("first", path)
    with pytest.raises(ReportError):
        write_text("second", path)
    write_text("second", path, overwrite=True)
    assert path.read_text(encoding="utf-8") == "second"
