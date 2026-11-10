"""Typed results and canonical serialization.

Every public result is a frozen dataclass. ``to_dict`` is the single source of
truth for JSON output, so tests and reports cannot drift from the library.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from upliftlab.errors import ReportError

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SRMResult:
    labels: tuple[str, ...]
    counts: tuple[int, ...]
    expected_counts: tuple[float, ...]
    chi_square: float
    p_value: float
    method: str
    alpha: float
    detected: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "labels": list(self.labels),
            "counts": list(self.counts),
            "expected_counts": list(self.expected_counts),
            "chi_square": None if math.isnan(self.chi_square) else self.chi_square,
            "p_value": self.p_value,
            "method": self.method,
            "alpha": self.alpha,
            "detected": self.detected,
        }


@dataclass(frozen=True, slots=True)
class BalanceRow:
    covariate: str
    treated_mean: float
    control_mean: float
    smd: float
    n_treated: int
    n_control: int

    def to_dict(self) -> dict[str, object]:
        return {
            "covariate": self.covariate,
            "treated_mean": self.treated_mean,
            "control_mean": self.control_mean,
            "smd": None if not math.isfinite(self.smd) else self.smd,
            "n_treated": self.n_treated,
            "n_control": self.n_control,
        }


@dataclass(frozen=True, slots=True)
class ATEResult:
    estimate: float
    standard_error: float
    ci_low: float
    ci_high: float
    p_value: float
    alpha: float
    n_treated: int
    n_control: int
    method: str

    def to_dict(self) -> dict[str, object]:
        return {
            "estimate": self.estimate,
            "standard_error": self.standard_error,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "p_value": self.p_value,
            "alpha": self.alpha,
            "n_treated": self.n_treated,
            "n_control": self.n_control,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    estimate: float
    ci_low: float
    ci_high: float
    n_bootstrap: int
    seed: int
    alpha: float

    def to_dict(self) -> dict[str, object]:
        return {
            "estimate": self.estimate,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "n_bootstrap": self.n_bootstrap,
            "seed": self.seed,
            "alpha": self.alpha,
        }


@dataclass(frozen=True, slots=True)
class CUPEDResult:
    theta: float
    raw: ATEResult
    adjusted: ATEResult
    variance_reduction: float
    correlation: float

    def to_dict(self) -> dict[str, object]:
        return {
            "theta": self.theta,
            "raw": self.raw.to_dict(),
            "adjusted": self.adjusted.to_dict(),
            "variance_reduction": self.variance_reduction,
            "correlation": self.correlation,
        }


@dataclass(frozen=True, slots=True)
class ReadoutResult:
    dataset: str
    dataset_sha256: str
    rows: int
    outcome: str
    covariate: str
    alpha: float
    seed: int
    bootstrap: int
    srm: SRMResult
    balance: tuple[BalanceRow, ...]
    ate: ATEResult
    bootstrap_result: BootstrapResult
    cuped: CUPEDResult
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset": self.dataset,
            "dataset_sha256": self.dataset_sha256,
            "rows": self.rows,
            "outcome": self.outcome,
            "covariate": self.covariate,
            "alpha": self.alpha,
            "seed": self.seed,
            "bootstrap": self.bootstrap,
            "srm": self.srm.to_dict(),
            "balance": [row.to_dict() for row in self.balance],
            "ate": self.ate.to_dict(),
            "bootstrap_result": self.bootstrap_result.to_dict(),
            "cuped": self.cuped.to_dict(),
            "caveats": list(self.caveats),
        }


def _atomic_write(path: Path, payload: str) -> None:
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        temporary = None
    except OSError as exc:
        raise ReportError(f"cannot write {path}: {exc}") from exc
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)


def write_json(result: dict[str, Any], path: Path, *, overwrite: bool = False) -> Path:
    """Write canonical JSON with sorted keys and no NaN tokens."""
    if path.exists() and not overwrite:
        raise ReportError(f"{path} exists; pass --force to overwrite")
    try:
        payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except ValueError as exc:
        raise ReportError(f"{path}: result contains a non-finite number") from exc
    _atomic_write(path, payload)
    return path


def write_text(text: str, path: Path, *, overwrite: bool = False) -> Path:
    """Write UTF-8 text atomically, refusing accidental overwrite."""
    if path.exists() and not overwrite:
        raise ReportError(f"{path} exists; pass --force to overwrite")
    _atomic_write(path, text)
    return path
