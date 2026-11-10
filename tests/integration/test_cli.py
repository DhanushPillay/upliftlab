"""CLI behavior through the public entry point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from upliftlab.cli import main
from upliftlab.errors import DataError


@pytest.fixture(autouse=True)
def _skip_checksum(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI fixtures are synthetic; checksum enforcement has its own unit test."""
    monkeypatch.setattr("upliftlab.datasets.verify_checksum", lambda *_args: None)


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "upliftlab" in capsys.readouterr().out


def test_analyze_writes_markdown_and_json(hillstrom_gz_path: Path, tmp_path: Path) -> None:
    data_dir = hillstrom_gz_path.parent
    report_path = tmp_path / "reports" / "hillstrom-readout.md"
    json_path = tmp_path / "results" / "hillstrom-readout.json"
    config_path = tmp_path / "readout.toml"
    config_path.write_text(
        '[readout]\noutcome = "visit"\ncovariate = "history"\n'
        "alpha = 0.05\nbootstrap = 200\nseed = 42\n",
        encoding="utf-8",
    )

    code = main(
        [
            "analyze",
            "hillstrom",
            "--data-dir",
            str(data_dir),
            "--config",
            str(config_path),
            "--out",
            str(report_path),
            "--json",
            str(json_path),
        ]
    )

    assert code == 0
    assert report_path.exists()
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["dataset"] == "hillstrom"
    assert payload["rows"] == 64_000
    assert "ate" in payload
    assert "cuped" in payload


def test_missing_data_returns_data_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["analyze", "hillstrom", "--data-dir", str(tmp_path)])
    assert code == 4
    assert "run 'upliftlab fetch hillstrom'" in capsys.readouterr().err


def test_fetch_prints_verified_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "hillstorm_no_indices.csv.gz"
    monkeypatch.setattr("upliftlab.cli.fetch_dataset", lambda *_args, **_kwargs: path)
    code = main(["fetch", "hillstrom", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "verified" in capsys.readouterr().out


def test_fetch_error_returns_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args: object, **kwargs: object) -> Path:
        raise DataError("download failed")

    monkeypatch.setattr("upliftlab.cli.fetch_dataset", fail)
    code = main(["fetch", "hillstrom", "--data-dir", str(tmp_path)])
    assert code == 4
    assert "download failed" in capsys.readouterr().err


def test_analyze_prints_markdown_when_no_output_path(
    hillstrom_gz_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "readout.toml"
    config_path.write_text("[readout]\nbootstrap = 200\n", encoding="utf-8")
    code = main(
        [
            "analyze",
            "hillstrom",
            "--data-dir",
            str(hillstrom_gz_path.parent),
            "--config",
            str(config_path),
        ]
    )
    assert code == 0
    assert "## Summary" in capsys.readouterr().out


def test_existing_output_requires_force(
    hillstrom_gz_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = tmp_path / "readout.md"
    report_path.write_text("occupied", encoding="utf-8")
    config_path = tmp_path / "readout.toml"
    config_path.write_text("[readout]\nbootstrap = 200\n", encoding="utf-8")
    code = main(
        [
            "analyze",
            "hillstrom",
            "--data-dir",
            str(hillstrom_gz_path.parent),
            "--config",
            str(config_path),
            "--out",
            str(report_path),
        ]
    )
    assert code == 5
    assert "--force" in capsys.readouterr().err


def test_config_error_returns_2(
    hillstrom_gz_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "readout.toml"
    config_path.write_text("[readout]\nalpha = 2.0\n", encoding="utf-8")
    code = main(
        [
            "analyze",
            "hillstrom",
            "--data-dir",
            str(hillstrom_gz_path.parent),
            "--config",
            str(config_path),
        ]
    )
    assert code == 2
    assert "alpha" in capsys.readouterr().err


def test_analysis_error_returns_6(
    hillstrom_gz_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "readout.toml"
    config_path.write_text('[readout]\noutcome = "not_a_column"\n', encoding="utf-8")
    code = main(
        [
            "analyze",
            "hillstrom",
            "--data-dir",
            str(hillstrom_gz_path.parent),
            "--config",
            str(config_path),
        ]
    )
    assert code == 6
    assert "not_a_column" in capsys.readouterr().err


def test_simulate_writes_json_and_markdown(tmp_path: Path) -> None:
    json_path = tmp_path / "bench.json"
    markdown_path = tmp_path / "results.md"
    code = main(
        [
            "simulate",
            "--scenario",
            "null",
            "--replications",
            "100",
            "--out",
            str(json_path),
            "--markdown",
            str(markdown_path),
        ]
    )
    assert code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["seed"] == 42
    assert len(payload["scenarios"]) == 1
    assert payload["scenarios"][0]["replications"] == 100
    assert "Simulation benchmark" in markdown_path.read_text(encoding="utf-8")


def test_simulate_prints_when_no_output_path(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["simulate", "--scenario", "null", "--replications", "100"])
    assert code == 0
    assert "Simulation benchmark" in capsys.readouterr().out


def test_simulate_rejects_few_replications(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["simulate", "--scenario", "null", "--replications", "50"])
    assert code == 6
    assert "at least 100" in capsys.readouterr().err


def test_simulate_rejects_negative_seed(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["simulate", "--scenario", "null", "--replications", "100", "--seed", "-1"])
    assert code == 6
    assert "non-negative" in capsys.readouterr().err


def test_simulate_existing_output_requires_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "bench.json"
    out.write_text("occupied", encoding="utf-8")
    code = main(
        [
            "simulate",
            "--scenario",
            "null",
            "--replications",
            "100",
            "--out",
            str(out),
        ]
    )
    assert code == 5
    assert "--force" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "occupied"


def test_simulate_rejects_same_output_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    same = tmp_path / "bench"
    code = main(
        [
            "simulate",
            "--scenario",
            "null",
            "--replications",
            "100",
            "--out",
            str(same),
            "--markdown",
            str(same),
        ]
    )
    assert code == 5
    assert "different paths" in capsys.readouterr().err
