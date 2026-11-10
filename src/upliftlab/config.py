"""Analysis configuration: frozen dataclasses, explicit validation."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from upliftlab.errors import ConfigError


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    outcome: str = "visit"
    covariate: str = "history"
    alpha: float = 0.05
    bootstrap: int = 2000
    seed: int = 42

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, str) or not self.outcome:
            raise ConfigError("outcome must be a non-empty string")
        if not isinstance(self.covariate, str) or not self.covariate:
            raise ConfigError("covariate must be a non-empty string")
        if isinstance(self.alpha, bool) or not isinstance(self.alpha, (int, float)):
            raise ConfigError("alpha must be a number")
        if not 0.0 < float(self.alpha) < 1.0:
            raise ConfigError("alpha must be strictly between 0 and 1")
        if isinstance(self.bootstrap, bool) or not isinstance(self.bootstrap, int):
            raise ConfigError("bootstrap must be an integer")
        if self.bootstrap < 100:
            raise ConfigError("bootstrap must be at least 100")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ConfigError("seed must be an integer")
        if self.seed < 0:
            raise ConfigError("seed must be non-negative")


_READOUT_KEYS = {"outcome", "covariate", "alpha", "bootstrap", "seed"}


def load_analysis_config(path: Path | None = None) -> AnalysisConfig:
    """Load ``[readout]`` from TOML, or return documented defaults."""
    if path is None:
        return AnalysisConfig()
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    section = raw.get("readout")
    if not isinstance(section, dict):
        raise ConfigError(f"{path} must contain a [readout] table")
    section = cast(dict[str, Any], section)
    unknown = set(section) - _READOUT_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"unknown [readout] keys in {path}: {names}")
    return AnalysisConfig(**section)
