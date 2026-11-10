"""FastAPI smoke and contract tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from upliftlab.api import main as api_main
from upliftlab.api import service
from upliftlab.datasets.base import Dataset
from upliftlab.datasets.hillstrom import HILLSTROM
from upliftlab.uplift import UpliftConfig, fit_uplift


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(api_main.app)


@pytest.fixture(scope="module")
def small_dataset(hillstrom_dataset: Dataset) -> Dataset:
    frame = hillstrom_dataset.frame.iloc[:12_000].copy()
    return Dataset(name="hillstrom", frame=frame, spec=HILLSTROM)


@pytest.fixture(scope="module")
def fitted(small_dataset: Dataset):  # type: ignore[no-untyped-def]
    config = UpliftConfig(
        outcome="visit",
        seed=5,
        max_iter=30,
        min_samples_leaf=20,
        policy_bootstrap=10,
    )
    return fit_uplift(small_dataset, config), config


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"]


def test_datasets_lists_hillstrom(client: TestClient) -> None:
    response = client.get("/api/datasets")
    assert response.status_code == 200
    assert response.json()["datasets"] == ["hillstrom"]


def test_overview_returns_readout_and_uplift(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    small_dataset: Dataset,
    fitted,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setattr(service, "_dataset", lambda *_: small_dataset)
    monkeypatch.setattr(service, "_fitted", lambda *_: fitted[0])

    response = client.post(
        "/api/overview",
        json={
            "dataset": "hillstrom",
            "outcome": "visit",
            "seed": 5,
            "alpha": 0.05,
            "bootstrap": 100,
            "budget_fraction": 0.2,
            "value_per_conversion": 2.0,
            "cost_per_contact": 0.05,
            "policy_bootstrap": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == 12_000
    assert payload["readout"]["outcome"] == "visit"
    assert payload["uplift"]["metrics"]["qini"] is not None
    assert len(payload["uplift"]["curve"]) == 101
    assert payload["uplift"]["policy"]["name"] == "uplift model"


def test_policy_reprices_without_refitting(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    small_dataset: Dataset,
    fitted,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setattr(service, "_dataset", lambda *_: small_dataset)
    monkeypatch.setattr(service, "_fitted", lambda *_: fitted[0])

    response = client.post(
        "/api/policy",
        json={
            "dataset": "hillstrom",
            "outcome": "visit",
            "seed": 5,
            "budget_fraction": 0.1,
            "value_per_conversion": 2.0,
            "cost_per_contact": 0.05,
            "policy_bootstrap": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy"]["budget_fraction"] == pytest.approx(0.1)
    assert len(payload["baselines"]) == 2


def test_overview_rejects_bad_budget(client: TestClient) -> None:
    response = client.post(
        "/api/overview",
        json={"budget_fraction": 0.0},
    )
    assert response.status_code == 422


def test_policy_rejects_two_budget_inputs(client: TestClient) -> None:
    response = client.post(
        "/api/policy",
        json={"budget_fraction": 0.2, "budget_dollars": 6.0},
    )
    assert response.status_code == 422
