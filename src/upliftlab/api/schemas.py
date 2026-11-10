"""Request and response contracts for the local API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OverviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str = "hillstrom"
    outcome: str = "visit"
    seed: int = Field(default=42, ge=0)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    bootstrap: int = Field(default=500, ge=100, le=5000)
    budget_fraction: float = Field(default=0.2, gt=0.0, le=1.0)
    value_per_conversion: float = Field(default=2.0, ge=0.0)
    cost_per_contact: float = Field(default=0.05, ge=0.0)
    policy_bootstrap: int = Field(default=200, ge=0, le=2000)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str = "hillstrom"
    outcome: str = "visit"
    seed: int = Field(default=42, ge=0)
    budget_fraction: float = Field(default=0.2, gt=0.0, le=1.0)
    value_per_conversion: float = Field(default=2.0, ge=0.0)
    cost_per_contact: float = Field(default=0.05, ge=0.0)
    policy_bootstrap: int = Field(default=200, ge=0, le=2000)
