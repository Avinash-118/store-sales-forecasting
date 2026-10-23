import os
import asyncio
from fastapi.concurrency import run_in_threadpool
from typing import List

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.pipelines.prediction_pipeline import PredictionPipeline

app = FastAPI()

# Files prediction_pipeline.py loads at request time (see the M2 fix log)
REQUIRED_ARTIFACTS = [
    "artifacts/trained_model.joblib",
    "artifacts/oil_model.joblib",
    "artifacts/covariates.joblib",
    "artifacts/timeseries_data.joblib",
]


class Covariate_params(BaseModel):
    store_nbr: int
    family: str
    horizon: int
    onpromotion: List[int]
    is_holiday: List[int]


@app.get("/healthz")
async def liveness():
    """Liveness: the process is up and can answer HTTP. No dependency checks."""
    return {"status": "alive"}


def check_database():
    """Run SELECT 1 using the team's state module (Key Vault + managed identity)."""
    from state import get_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        conn.close()


@app.get("/readyz")
def readiness():
    """Readiness: model artifacts exist AND the database is reachable."""
    missing = [p for p in REQUIRED_ARTIFACTS if not os.path.exists(p)]
    if missing:
        return JSONResponse(status_code=503,
                            content={"status": "not ready", "missing_artifacts": missing})
    try:
        check_database()
    except Exception as e:
        return JSONResponse(status_code=503,
                            content={"status": "not ready", "database": str(e)[:200]})
    return {"status": "ready", "model": "loaded", "database": "ok"}


# One forecast at a time per pod: each forecast loads the model into memory,
# so running many in parallel OOM-kills the pod. Extra requests wait in line,
# and the HPA adds pods when CPU rises. The event loop stays free, so
# /healthz still answers instantly while a forecast is running.
FORECAST_SLOTS = asyncio.Semaphore(int(os.getenv("FORECAST_CONCURRENCY", "1")))


def _run_forecast(params):
    pipeline_obj = PredictionPipeline()
    return pipeline_obj.produce_forecasts(
        store_nbr=params.store_nbr,
        family=params.family,
        horizon=params.horizon,
        onpromotion=params.onpromotion,
        is_holiday=params.is_holiday,
    )


@app.post("/")
async def get_forecasts(params: Covariate_params):
    async with FORECAST_SLOTS:
        return await run_in_threadpool(_run_forecast, params)