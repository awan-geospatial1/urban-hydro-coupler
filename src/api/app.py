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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.coupler.core import HydroCoupler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Urban Hydro-Coupler API",
    description="Couples regional hydrological model output (Wflow) with SWMM.",
    version="0.1.0",
)


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
