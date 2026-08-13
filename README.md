# 🌊 Urban Hydro-Coupler

A Python framework that couples a regional hydrological model (e.g.
[Wflow](https://github.com/Deltares/Wflow.jl), via the
[`hydrological_modelling`](https://github.com/awan-geospatial1/hydrological_modelling)
project) with the EPA Stormwater Management Model (SWMM) to simulate urban
flooding under changing upstream conditions.

## Why

Urban watersheds are increasingly flooding because upstream rural runoff
reaches urban drainage systems faster and in higher volumes as climate and
land use change, while sewers and storm drains are often sized for
conditions that no longer hold. Rural and urban models are usually run in
isolation, missing the connection between them. Urban Hydro-Coupler bridges
that gap by injecting regional streamflow directly into an urban SWMM model
as a dynamic boundary condition — from hillslope to sewer.

See [`docs/architecture.md`](docs/architecture.md) for the full data flow
and technology stack.

## Installation

```bash
git clone https://github.com/awan-geospatial1/urban-hydro-coupler.git
cd urban-hydro-coupler
pip install -e ".[dev]"
```

Requires Python 3.9+. SWMM simulation requires `pyswmm`, which is installed
as a core dependency.

## Quickstart

Generate a sample Wflow output and run the bundled example SWMM model:

```bash
python scripts/generate_sample_model.py --out data/processed/wflow_output.csv --days 30

python scripts/run_coupling.py \
    --swmm data/raw/example_model.inp \
    --wflow data/processed/wflow_output.csv \
    --node Node1
```

Or use the class directly:

```python
from pathlib import Path
from src.coupler.core import HydroCoupler

coupler = HydroCoupler(
    swmm_input_path=Path("data/raw/example_model.inp"),
    wflow_output_path=Path("data/processed/wflow_output.csv"),
    target_node="Node1",
)
results = coupler.run_coupled_simulation()
print(results["flooding_summary"])
```

### Dashboard

```bash
streamlit run src/dashboard/streamlit_app.py
```

Upload a SWMM `.inp` and a Wflow output CSV, pick the target node, and run
the coupled simulation from the browser.

### API

```bash
uvicorn src.api.app:app --reload
```

```bash
curl -X POST http://localhost:8000/simulate \
    -F "swmm_file=@data/raw/example_model.inp" \
    -F "wflow_file=@data/processed/wflow_output.csv" \
    -F "target_node=Node1"
```

### Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

This starts the dashboard on `http://localhost:8501` and the API on
`http://localhost:8000`.

## Input format

The Wflow output CSV must have two columns:

| column | description |
|---|---|
| `time` | timestamp (any format `pandas.to_datetime` accepts) |
| `streamflow` | flow rate, in the units your SWMM model expects |

Timestamps are always normalized to UTC internally — see
[`docs/architecture.md`](docs/architecture.md#why-timezone-handling-gets-special-treatment)
for why that matters.

## Testing

```bash
pytest --cov=./ --cov-report=term-missing
```

Tests that require `pyswmm`'s simulation engine (`test_model_runner.py`)
skip automatically if it isn't installed.

## Project layout

```
urban-hydro-coupler/
├── src/coupler/        # HydroCoupler core, model runner, utils
├── src/api/             # FastAPI app
├── src/dashboard/       # Streamlit dashboard
├── scripts/              # CLI entry points
├── tests/                 # pytest suite
├── data/raw/               # sample SWMM .inp
├── data/processed/          # generated Wflow CSVs (gitignored)
├── docker/                    # Dockerfile + docker-compose.yml
└── docs/                       # architecture and reference docs
```

## Related work

- [`hydrological_modelling`](https://github.com/awan-geospatial1/hydrological_modelling) — the Wflow automation pipeline this project consumes output from.
- [`climate-downscaling`](https://github.com/awan-geospatial1/climate-downscaling) — CMIP6 bias correction feeding into the above.

## References

- McDonnell, B. E., et al. (2020). PySWMM: The Python Interface to
  Stormwater Management Model (SWMM). *Journal of Open Source Software*,
  5(52), 2292.

## License

MIT — see [`LICENSE`](LICENSE).
