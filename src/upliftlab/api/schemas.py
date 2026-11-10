"""Request and response contracts for the local API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _BudgetRequest(BaseModel):
    budget_fraction: float = Field(default=0.2, gt=0.0, le=1.0)
    budget_dollars: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _one_budget_input(self) -> _BudgetRequest:
        if "budget_fraction" in self.model_fields_set and "budget_dollars" in self.model_fields_set:
            raise ValueError("budget_fraction and budget_dollars are mutually exclusive")
        return self


class OverviewRequest(_BudgetRequest):
    model_config = ConfigDict(extra="forbid")

    dataset: str = "hillstrom"
    outcome: str = "visit"
    seed: int = Field(default=42, ge=0)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    bootstrap: int = Field(default=500, ge=100, le=5000)
    value_per_conversion: float = Field(default=2.0, ge=0.0)
    cost_per_contact: float = Field(default=0.05, ge=0.0)
    policy_bootstrap: int = Field(default=200, ge=0, le=2000)


class PolicyRequest(_BudgetRequest):
    model_config = ConfigDict(extra="forbid")

    dataset: str = "hillstrom"
    outcome: str = "visit"
    seed: int = Field(default=42, ge=0)
    value_per_conversion: float = Field(default=2.0, ge=0.0)
    cost_per_contact: float = Field(default=0.05, ge=0.0)
    policy_bootstrap: int = Field(default=200, ge=0, le=2000)
