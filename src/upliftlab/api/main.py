"""FastAPI app for the local uplift dashboard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from upliftlab import __version__
from upliftlab.api.schemas import OverviewRequest, PolicyRequest
from upliftlab.api.service import overview, policy
from upliftlab.datasets import available_datasets
from upliftlab.errors import (
    AnalysisError,
    ChecksumError,
    ConfigError,
    DataError,
    ReportError,
    SchemaError,
    UpliftError,
)

STATIC_DIR = Path(os.environ.get("UPLIFTLAB_STATIC_DIR", "web/dist"))

app = FastAPI(
    title="upliftlab",
    version=__version__,
    description="Experiment readout and budget-constrained uplift targeting.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _status_for(exc: UpliftError) -> int:
    if isinstance(exc, ChecksumError):
        return 409
    if isinstance(exc, (ConfigError, AnalysisError, SchemaError)):
        return 422
    if isinstance(exc, DataError):
        return 400
    if isinstance(exc, ReportError):
        return 500
    return 500


@app.exception_handler(UpliftError)
async def uplift_error_handler(_request: Request, exc: UpliftError) -> JSONResponse:
    return JSONResponse(
        status_code=_status_for(exc),
        content={"detail": str(exc), "type": type(exc).__name__},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/datasets")
def datasets() -> dict[str, object]:
    return {"datasets": list(available_datasets())}


@app.post("/api/overview")
def api_overview(body: OverviewRequest) -> dict[str, Any]:
    return overview(**body.model_dump())


@app.post("/api/policy")
def api_policy(body: PolicyRequest) -> dict[str, Any]:
    return policy(**body.model_dump())


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "upliftlab",
            "docs": "/docs",
            "note": "Run `npm run build` in web/ or set UPLIFTLAB_STATIC_DIR.",
        }
