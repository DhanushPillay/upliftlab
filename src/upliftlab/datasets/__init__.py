"""Dataset registry and public loading helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from upliftlab.datasets.base import Dataset, DatasetSpec
from upliftlab.datasets.fetch import download_dataset, verify_checksum
from upliftlab.datasets.hillstrom import HILLSTROM, load_hillstrom
from upliftlab.errors import DataError

REGISTRY: Mapping[str, DatasetSpec] = MappingProxyType(
    {
        "hillstrom": HILLSTROM,
    }
)


def available_datasets() -> tuple[str, ...]:
    return tuple(sorted(REGISTRY))


def get_spec(name: str) -> DatasetSpec:
    try:
        return REGISTRY[name]
    except KeyError:
        options = ", ".join(available_datasets())
        raise DataError(f"unknown dataset {name!r}; choose one of: {options}") from None


def fetch_dataset(
    name: str,
    data_dir: Path = Path("data/raw"),
    *,
    force: bool = False,
) -> Path:
    return download_dataset(get_spec(name), data_dir, force=force)


def load_dataset(name: str, data_dir: Path = Path("data/raw")) -> Dataset:
    spec = get_spec(name)
    path = data_dir / spec.filename
    if not path.exists():
        raise DataError(f"{path} is missing; run 'upliftlab fetch {name}' first")
    verify_checksum(path, spec.sha256)
    if name == "hillstrom":
        return load_hillstrom(path)
    raise DataError(f"no loader registered for {name!r}")


def ensure_dataset(name: str, data_dir: Path = Path("data/raw")) -> Dataset:
    """Load a verified dataset, downloading it once when the cache is empty."""
    spec = get_spec(name)
    if not (data_dir / spec.filename).exists():
        fetch_dataset(name, data_dir)
    return load_dataset(name, data_dir)


__all__ = [
    "Dataset",
    "DatasetSpec",
    "available_datasets",
    "ensure_dataset",
    "fetch_dataset",
    "get_spec",
    "load_dataset",
]
