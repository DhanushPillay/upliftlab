"""Configuration parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from upliftlab.config import AnalysisConfig, load_analysis_config
from upliftlab.errors import ConfigError


def test_defaults_are_valid() -> None:
    config = AnalysisConfig()
    assert config.outcome == "visit"
    assert config.bootstrap >= 100


def test_load_readout_config(tmp_path: Path) -> None:
    path = tmp_path / "readout.toml"
    path.write_text(
        '[readout]\noutcome = "conversion"\ncovariate = "history"\n'
        "alpha = 0.1\nbootstrap = 250\nseed = 7\n",
        encoding="utf-8",
    )
    config = load_analysis_config(path)
    assert config.outcome == "conversion"
    assert config.alpha == 0.1
    assert config.bootstrap == 250
    assert config.seed == 7


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "readout.toml"
    path.write_text("[readout]\nalpha = 0.05\nsurprise = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown"):
        load_analysis_config(path)


def test_alpha_must_be_in_range() -> None:
    with pytest.raises(ConfigError):
        AnalysisConfig(alpha=1.5)


def test_bootstrap_must_be_large_enough() -> None:
    with pytest.raises(ConfigError):
        AnalysisConfig(bootstrap=10)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outcome": ""},
        {"covariate": ""},
        {"alpha": True},
        {"bootstrap": True},
        {"seed": True},
    ],
)
def test_invalid_config_types(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        AnalysisConfig(**kwargs)


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_analysis_config(tmp_path / "missing.toml")


def test_missing_readout_table(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[other]\nalpha = 0.05\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"\[readout\]"):
        load_analysis_config(path)


def test_readout_must_be_a_table(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("readout = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"\[readout\]"):
        load_analysis_config(path)
