"""Shared pytest fixtures for the Urban Hydro-Coupler test suite."""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture
def sample_swmm_path() -> Path:
    """Path to the bundled minimal SWMM .inp file."""
    return ROOT / "data" / "raw" / "example_model.inp"


@pytest.fixture
def wflow_csv(tmp_path: Path) -> Path:
    """A small, well-formed Wflow output CSV."""
    df = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=48, freq="h", tz="UTC"),
            "streamflow": [5.0 + (i % 6) for i in range(48)],
        }
    )
    path = tmp_path / "wflow_output.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def wflow_csv_naive_time(tmp_path: Path) -> Path:
    """A Wflow CSV with timezone-naive timestamps."""
    df = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=24, freq="h"),
            "streamflow": [3.0] * 24,
        }
    )
    path = tmp_path / "wflow_naive.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def wflow_csv_with_issues(tmp_path: Path) -> Path:
    """A Wflow CSV containing missing values and a negative flow."""
    df = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=6, freq="h", tz="UTC"),
            "streamflow": [1.0, None, 3.0, -2.0, 5.0, 6.0],
        }
    )
    path = tmp_path / "wflow_issues.csv"
    df.to_csv(path, index=False)
    return path
