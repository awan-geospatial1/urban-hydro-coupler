"""Tests for src.coupler.core.HydroCoupler."""
from pathlib import Path

import pandas as pd
import pytest

from src.coupler.core import HydroCoupler


def test_init_raises_on_missing_swmm_file(tmp_path: Path, wflow_csv: Path):
    """A missing SWMM path should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        HydroCoupler(
            swmm_input_path=tmp_path / "does_not_exist.inp",
            wflow_output_path=wflow_csv,
        )


def test_init_raises_on_missing_wflow_file(sample_swmm_path: Path, tmp_path: Path):
    """A missing Wflow path should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        HydroCoupler(
            swmm_input_path=sample_swmm_path,
            wflow_output_path=tmp_path / "does_not_exist.csv",
        )


def test_load_wflow_flow_converts_to_utc(sample_swmm_path: Path, wflow_csv_naive_time: Path):
    """Timezone-naive timestamps should be localized to UTC on load."""
    coupler = HydroCoupler(
        swmm_input_path=sample_swmm_path,
        wflow_output_path=wflow_csv_naive_time,
        target_node="Node1",
    )
    assert coupler.wflow_flow.index.tz is not None
    assert str(coupler.wflow_flow.index.tz) == "UTC"


def test_load_wflow_flow_handles_missing_and_negative(
    sample_swmm_path: Path, wflow_csv_with_issues: Path
):
    """Missing values are interpolated and negative flows are clipped to 0."""
    coupler = HydroCoupler(
        swmm_input_path=sample_swmm_path,
        wflow_output_path=wflow_csv_with_issues,
        target_node="Node1",
    )
    assert not coupler.wflow_flow.isnull().any()
    assert (coupler.wflow_flow >= 0).all()


def test_load_wflow_flow_missing_columns_raises(sample_swmm_path: Path, tmp_path: Path):
    """A CSV lacking the required columns should raise ValueError."""
    bad_csv = tmp_path / "bad.csv"
    pd.DataFrame({"foo": [1, 2], "bar": [3, 4]}).to_csv(bad_csv, index=False)

    with pytest.raises(ValueError):
        HydroCoupler(
            swmm_input_path=sample_swmm_path,
            wflow_output_path=bad_csv,
            target_node="Node1",
        )


def test_load_wflow_flow_empty_file_raises(sample_swmm_path: Path, tmp_path: Path):
    """An empty Wflow CSV (headers only) should raise ValueError."""
    empty_csv = tmp_path / "empty.csv"
    pd.DataFrame({"time": [], "streamflow": []}).to_csv(empty_csv, index=False)

    with pytest.raises(ValueError):
        HydroCoupler(
            swmm_input_path=sample_swmm_path,
            wflow_output_path=empty_csv,
            target_node="Node1",
        )


def test_flow_for_time_exact_match(sample_swmm_path: Path, wflow_csv: Path):
    """An exact timestamp match returns the corresponding flow value."""
    coupler = HydroCoupler(
        swmm_input_path=sample_swmm_path,
        wflow_output_path=wflow_csv,
        target_node="Node1",
    )
    first_time = coupler.wflow_flow.index[0]
    expected = coupler.wflow_flow.iloc[0]
    assert coupler._flow_for_time(first_time) == pytest.approx(expected)


def test_flow_for_time_nearest_fallback(sample_swmm_path: Path, wflow_csv: Path):
    """A timestamp not in the index falls back to the nearest available one."""
    coupler = HydroCoupler(
        swmm_input_path=sample_swmm_path,
        wflow_output_path=wflow_csv,
        target_node="Node1",
    )
    off_time = coupler.wflow_flow.index[0] + pd.Timedelta(minutes=1)
    value = coupler._flow_for_time(off_time)
    assert value == pytest.approx(coupler.wflow_flow.iloc[0])


def test_flow_for_time_empty_series_returns_zero(sample_swmm_path: Path, tmp_path: Path):
    """An empty (but valid-schema) series should safely return 0.0."""
    coupler = HydroCoupler.__new__(HydroCoupler)
    coupler.wflow_flow = pd.Series(dtype=float)
    assert coupler._flow_for_time(pd.Timestamp.now(tz="UTC")) == 0.0
