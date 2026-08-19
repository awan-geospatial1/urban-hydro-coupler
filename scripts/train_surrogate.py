#!/usr/bin/env python3
"""Train the ML flood-risk surrogate model.

Generates a batch of synthetic Wflow streamflow scenarios spanning a range
of magnitudes, timings, and "flashiness", runs each one through the full
coupled Wflow -> SWMM simulation (the ground truth), extracts hydrograph
features from the input series, and trains a ``FloodSurrogateModel`` to
predict peak node depth from those features alone -- so future scenarios
can be screened without rerunning SWMM.

Usage:
    python scripts/train_surrogate.py \\
        --swmm data/raw/example_model.inp \\
        --node Node1 \\
        --n-scenarios 60 \\
        --out models/flood_surrogate.joblib

Requires pyswmm to be installed (it's a core dependency of this project).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from src.coupler.core import HydroCoupler  # noqa: E402
from src.ml.features import extract_flow_features  # noqa: E402
from src.ml.surrogate import FloodSurrogateModel  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Train the flood-risk ML surrogate model.")
    parser.add_argument("--swmm", required=True, type=Path, help="Path to SWMM .inp file")
    parser.add_argument("--node", default="Node1", help="Target SWMM node for inflow injection")
    parser.add_argument(
        "--n-scenarios", type=int, default=60, help="Number of synthetic training scenarios"
    )
    parser.add_argument("--days", type=int, default=30, help="Days simulated per scenario")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("models/flood_surrogate.joblib"),
        help="Where to save the trained surrogate model",
    )
    parser.add_argument(
        "--keep-scenarios",
        action="store_true",
        help="Keep the generated per-scenario Wflow CSVs instead of deleting them",
    )
    return parser.parse_args()


def make_scenario(rng: np.random.Generator, days: int) -> pd.Series:
    """Generate one synthetic streamflow scenario with a randomized shape.

    Varies baseflow, storm peak magnitude/timing, and storm width so the
    resulting training set spans calm baseflow periods through sharp,
    flashy storm-driven hydrographs -- the same range of behavior a real
    ensemble of Wflow outputs (e.g. across climate scenarios) would show.

    Args:
        rng: NumPy random generator (for reproducibility).
        days: Number of days to simulate, at hourly resolution.

    Returns:
        Streamflow series indexed by UTC hourly timestamps.
    """
    mean_flow = rng.uniform(2, 15)
    storm_magnitude = rng.uniform(0, 60)
    storm_day = rng.integers(0, days)
    storm_width_days = rng.uniform(0.5, 4.0)

    t = np.arange(days * 24)  # hourly steps
    storm_center = storm_day * 24
    storm = storm_magnitude * np.exp(-0.5 * ((t - storm_center) / (storm_width_days * 24)) ** 2)
    noise = rng.normal(0, 0.5, size=t.size)
    flow = np.maximum(0.0, mean_flow + storm + noise)

    times = pd.date_range("2020-01-01", periods=t.size, freq="h", tz="UTC")
    return pd.Series(flow, index=times, name="streamflow")


def main() -> int:
    """Generate training scenarios, run the coupled model, and train+save the surrogate."""
    args = parse_args()

    rng = np.random.default_rng(args.seed)
    feature_rows = []
    targets = []

    tmp_dir = Path("data/processed/_surrogate_training")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for i in range(args.n_scenarios):
        flow = make_scenario(rng, days=args.days)
        wflow_path = tmp_dir / f"scenario_{i:03d}.csv"
        flow.rename_axis("time").reset_index(name="streamflow").to_csv(wflow_path, index=False)

        try:
            coupler = HydroCoupler(
                swmm_input_path=args.swmm, wflow_output_path=wflow_path, target_node=args.node
            )
            results = coupler.run_coupled_simulation()
        except Exception as exc:  # pragma: no cover - depends on pyswmm engine availability
            print(f"[{i + 1}/{args.n_scenarios}] scenario failed, skipping: {exc}", file=sys.stderr)
            continue
        finally:
            if not args.keep_scenarios:
                wflow_path.unlink(missing_ok=True)

        max_depth = results["flooding_summary"]["max_depth"]
        feature_rows.append(extract_flow_features(flow))
        targets.append(max_depth)
        print(f"[{i + 1}/{args.n_scenarios}] max_depth={max_depth:.3f}")

    if len(feature_rows) < 5:
        print(
            "Not enough successful scenarios to train a surrogate model "
            "(need >= 5). Check that pyswmm and its simulation engine are "
            "installed correctly.",
            file=sys.stderr,
        )
        return 1

    features_df = pd.DataFrame(feature_rows)
    target_series = pd.Series(targets)

    model = FloodSurrogateModel()
    metrics = model.train(features_df, target_series)
    print("Validation metrics:", metrics)

    model.save(args.out)
    print(f"Surrogate model saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
