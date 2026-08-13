#!/usr/bin/env python3
"""Generate a sample Wflow output CSV for testing and demos.

Usage:
    python scripts/generate_sample_model.py --out data/processed/wflow_output.csv
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.coupler.utils import create_sample_wflow_output  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate a sample Wflow output CSV.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/wflow_output.csv"),
        help="Output CSV path",
    )
    parser.add_argument("--start-date", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=365, help="Number of daily steps")
    parser.add_argument("--mean-flow", type=float, default=10.0, help="Mean streamflow (cms)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def main() -> None:
    """Generate and save the sample CSV."""
    args = parse_args()
    create_sample_wflow_output(
        output_path=args.out,
        start_date=args.start_date,
        days=args.days,
        mean_flow=args.mean_flow,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
