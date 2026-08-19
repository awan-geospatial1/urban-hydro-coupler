# Urban Hydro-Coupler — Documentation

## What this project does

Urban Hydro-Coupler bridges a regional hydrological model (Wflow) and the
EPA Stormwater Management Model (SWMM), so that upstream streamflow can
drive urban drainage simulations directly instead of being modeled in
isolation.

## Where to start

- [Architecture](architecture.md) — data flow and component overview.
- `README.md` (project root) — installation, quickstart, and usage.
- `src/coupler/core.py` — the `HydroCoupler` class docstrings are the
  canonical API reference; every public method is documented there.

## Module map

| Module | Purpose |
|---|---|
| `src/coupler/core.py` | `HydroCoupler` — loads Wflow output, validates it, injects it into a running SWMM simulation. |
| `src/coupler/model_runner.py` | Thin PySWMM wrappers for plain simulation runs and binary `.out` extraction, used outside the full coupling flow. |
| `src/coupler/utils.py` | Config loading, timezone normalization, sample data generation, outlier detection. |
| `src/api/app.py` | FastAPI service exposing `/simulate` for programmatic access. |
| `src/dashboard/streamlit_app.py` | Interactive upload-and-run dashboard. |
| `scripts/run_coupling.py` | CLI entry point for a single coupled run. |
| `scripts/generate_sample_model.py` | Generates a synthetic Wflow output CSV for testing. |

## Running things

- API: `uvicorn src.api.app:app --reload` then POST to `http://localhost:8000/simulate`.
- Dashboard: `streamlit run src/dashboard/streamlit_app.py`.
- CLI: `python scripts/run_coupling.py --swmm <path> --wflow <path> --node <name>`.
- Docker: `docker compose -f docker/docker-compose.yml up --build`.
