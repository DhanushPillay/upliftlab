"""Shared synthetic fixtures. No upstream data is committed or redistributed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from upliftlab.datasets.base import Dataset
from upliftlab.datasets.hillstrom import HILLSTROM


@pytest.fixture(scope="session")
def hillstrom_frame() -> pd.DataFrame:
    rng = np.random.default_rng(20261110)
    n = 64_000
    segment = rng.choice(
        ["No E-Mail", "Mens E-Mail", "Womens E-Mail"],
        size=n,
        p=[1 / 3, 1 / 3, 1 / 3],
    )
    treatment = (segment != "No E-Mail").astype("int8")
    history = rng.gamma(shape=2.0, scale=60.0, size=n)
    recency = rng.integers(1, 13, size=n, dtype=np.int64)
    mens = rng.integers(0, 2, size=n, dtype=np.int8)
    womens = rng.integers(0, 2, size=n, dtype=np.int8)
    newbie = rng.integers(0, 2, size=n, dtype=np.int8)
    history_segment = pd.cut(
        history,
        bins=[-np.inf, 100, 200, 350, 500, 750, 1000, np.inf],
        labels=[
            "1) $0 - $100",
            "2) $100 - $200",
            "3) $200 - $350",
            "4) $350 - $500",
            "5) $500 - $750",
            "6) $750 - $1,000",
            "7) $1,000 +",
        ],
    ).astype("string")
    zip_code = rng.choice(["Urban", "Surburban", "Rural"], size=n)
    channel = rng.choice(["Phone", "Web", "Multichannel"], size=n)

    visit_logit = -1.6 + 0.35 * treatment + 0.002 * history
    conversion_logit = -3.4 + 0.25 * treatment + 0.001 * history
    visit = rng.binomial(1, 1.0 / (1.0 + np.exp(-visit_logit)))
    conversion = rng.binomial(1, 1.0 / (1.0 + np.exp(-conversion_logit)))
    spend = np.where(conversion == 1, rng.gamma(shape=2.0, scale=30.0, size=n), 0.0)

    return pd.DataFrame(
        {
            "recency": recency,
            "history_segment": history_segment,
            "history": history,
            "mens": mens,
            "womens": womens,
            "zip_code": zip_code,
            "newbie": newbie,
            "channel": channel,
            "segment": segment,
            "visit": visit.astype("int8"),
            "conversion": conversion.astype("int8"),
            "spend": spend.astype("float64"),
        }
    )


@pytest.fixture(scope="session")
def hillstrom_dataset(hillstrom_frame: pd.DataFrame) -> Dataset:
    frame = hillstrom_frame.assign(
        treatment=(hillstrom_frame["segment"] != "No E-Mail").astype("int8")
    )
    return Dataset(name="hillstrom", frame=frame, spec=HILLSTROM)


@pytest.fixture(scope="session")
def hillstrom_gz_path(
    tmp_path_factory: pytest.TempPathFactory, hillstrom_frame: pd.DataFrame
) -> Path:
    directory = tmp_path_factory.mktemp("hillstrom")
    path = directory / HILLSTROM.filename
    hillstrom_frame.to_csv(path, index=False, compression="gzip")
    return path
