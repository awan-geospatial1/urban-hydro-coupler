"""FastAPI application for the Urban Hydro-Coupler.

Exposes a REST endpoint that accepts a SWMM ``.inp`` file and a Wflow output
CSV, runs the coupled simulation, and returns a JSON summary.

Run locally with:
    uvicorn src.api.app:app --reload
"""
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.coupler.core import HydroCoupler
from src.coupler.utils import validate_timezone
from src.ml.surrogate import FloodSurrogateModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Urban Hydro-Coupler API",
    description="Couples regional hydrological model output (Wflow) with SWMM.",
    version="0.1.0",
)

# Path to the trained ML surrogate model (see scripts/train_surrogate.py).
# Loaded lazily and cached on first use of /predict.
SURROGATE_MODEL_PATH = Path("models/flood_surrogate.joblib")
_surrogate_cache: Optional[FloodSurrogateModel] = None


def _get_surrogate_model() -> FloodSurrogateModel:
    """Load and cache the trained surrogate model.

    Raises:
        FileNotFoundError: If no trained model exists yet at
            ``SURROGATE_MODEL_PATH``.
    """
    global _surrogate_cache
    if _surrogate_cache is None:
        _surrogate_cache = FloodSurrogateModel.load(SURROGATE_MODEL_PATH)
    return _surrogate_cache


@app.get("/health")
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}


@app.post("/simulate")
async def simulate(
    swmm_file: UploadFile = File(..., description="SWMM .inp model file"),
    wflow_file: UploadFile = File(..., description="Wflow output CSV (time, streamflow)"),
    target_node: str = Form("Node1", description="SWMM node to receive the inflow"),
) -> JSONResponse:
    """Run a coupled SWMM/Wflow simulation from uploaded files.

    Args:
        swmm_file: SWMM ``.inp`` model file.
        wflow_file: Wflow output CSV with ``time`` and ``streamflow`` columns.
        target_node: SWMM node name to receive the inflow.

    Returns:
        JSON with the simulation results, or an error payload on failure.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        swmm_path = tmp_dir_path / "model.inp"
        wflow_path = tmp_dir_path / "wflow_output.csv"

        with open(swmm_path, "wb") as f:
            shutil.copyfileobj(swmm_file.file, f)
        with open(wflow_path, "wb") as f:
            shutil.copyfileobj(wflow_file.file, f)

        try:
            coupler = HydroCoupler(
                swmm_input_path=swmm_path,
                wflow_output_path=wflow_path,
                target_node=target_node,
            )
            results = coupler.run_coupled_simulation()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive catch-all
            logger.exception("Unexpected simulation failure")
            raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc

        # node_depths holds (timestamp, depth) tuples which aren't natively
        # JSON serializable — convert timestamps to ISO strings.
        results["node_depths"] = [
            {"time": str(t), "depth": d} for t, d in results.get("node_depths", [])
        ]

        return JSONResponse(content=results)


@app.post("/predict")
async def predict(
    wflow_file: UploadFile = File(..., description="Wflow output CSV (time, streamflow)"),
) -> JSONResponse:
    """Instantly screen a streamflow scenario with the ML surrogate model.

    Unlike ``/simulate``, this skips the full coupled SWMM run entirely and
    instead predicts peak node depth (plus a coarse risk level) directly
    from hydrograph features, in milliseconds rather than minutes. Useful
    for triaging large scenario ensembles -- confirm anything flagged
    medium/high risk with a full ``/simulate`` call.

    Requires a trained surrogate model at ``models/flood_surrogate.joblib``
    (see ``scripts/train_surrogate.py``).

    Args:
        wflow_file: Wflow output CSV with ``time`` and ``streamflow`` columns.

    Returns:
        JSON with ``predicted_max_depth``, ``risk_level``, and the
        extracted hydrograph ``features`` used for the prediction.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        wflow_path = Path(tmp_dir) / "wflow_output.csv"
        with open(wflow_path, "wb") as f:
            shutil.copyfileobj(wflow_file.file, f)

        try:
            df = pd.read_csv(wflow_path, parse_dates=["time"])
            if "time" not in df.columns or "streamflow" not in df.columns:
                raise ValueError("Wflow output must have 'time' and 'streamflow' columns")
            df = validate_timezone(df)
            flow = df.set_index("time")["streamflow"].sort_index()

            model = _get_surrogate_model()
            prediction = model.predict_from_series(flow)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Surrogate model not trained yet. Run "
                    f"scripts/train_surrogate.py first. ({exc})"
                ),
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive catch-all
            logger.exception("Unexpected surrogate prediction failure")
            raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc

        return JSONResponse(content=prediction)
