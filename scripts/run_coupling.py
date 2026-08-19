#!/usr/bin/env python3
"""CLI entry point to run a coupled Wflow -> SWMM simulation.

Usage:
    python scripts/run_coupling.py --swmm data/raw/example_model.inp \
        --wflow data/processed/wflow_output.csv --node Outfall1
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.coupler.core import HydroCoupler  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run a coupled Wflow -> SWMM simulation.")
    parser.add_argument("--swmm", required=True, type=Path, help="Path to SWMM .inp file")
    parser.add_argument("--wflow", required=True, type=Path, help="Path to Wflow output CSV")
    parser.add_argument("--node", default="Node1", help="Target SWMM node for inflow injection")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the results JSON summary",
    )
    return parser.parse_args()


def main() -> int:
    """Run the coupling from CLI args. Returns a process exit code."""
    args = parse_args()

    try:
        coupler = HydroCoupler(
            swmm_input_path=args.swmm,
            wflow_output_path=args.wflow,
            target_node=args.node,
        )
        results = coupler.run_coupled_simulation()
    except Exception as exc:
        print(f"Simulation failed: {exc}", file=sys.stderr)
        return 1

    summary = {
        "flooding_summary": results.get("flooding_summary"),
        "simulation_time": results.get("simulation_time"),
    }
    print(json.dumps(summary, indent=2, default=str))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
