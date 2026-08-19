"""Tests for src.coupler.utils."""
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.coupler.utils import (
    create_sample_wflow_output,
    detect_outliers,
    load_config,
    validate_timezone,
)


def test_load_config_yaml(tmp_path: Path):
    """A YAML config file loads into a matching dict."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"target_node": "Node1", "days": 30}))
    cfg = load_config(cfg_path)
    assert cfg == {"target_node": "Node1", "days": 30}


def test_load_config_json(tmp_path: Path):
    """A JSON config file loads into a matching dict."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_node": "Node1"}))
    cfg = load_config(cfg_path)
    assert cfg == {"target_node": "Node1"}


def test_load_config_missing_file_raises(tmp_path: Path):
    """A missing config path should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_load_config_unsupported_extension_raises(tmp_path: Path):
    """An unsupported extension should raise ValueError."""
    bad_path = tmp_path / "config.txt"
    bad_path.write_text("target_node: Node1")
    with pytest.raises(ValueError):
        load_config(bad_path)


def test_validate_timezone_localizes_naive():
    """A naive datetime column gets localized to UTC."""
    df = pd.DataFrame({"time": pd.date_range("2020-01-01", periods=3, freq="D")})
    out = validate_timezone(df)
    assert str(out["time"].dt.tz) == "UTC"


def test_validate_timezone_converts_other_tz():
    """A non-UTC tz-aware column gets converted to UTC."""
    df = pd.DataFrame(
        {"time": pd.date_range("2020-01-01", periods=3, freq="D", tz="US/Eastern")}
    )
    out = validate_timezone(df)
    assert str(out["time"].dt.tz) == "UTC"


def test_validate_timezone_missing_column_raises():
    """Requesting a column that doesn't exist should raise ValueError."""
    df = pd.DataFrame({"other": [1, 2, 3]})
    with pytest.raises(ValueError):
        validate_timezone(df)


def test_create_sample_wflow_output(tmp_path: Path):
    """The generated sample CSV has the right shape and non-negative flows."""
    out_path = tmp_path / "sample.csv"
    create_sample_wflow_output(out_path, days=10, seed=1)

    assert out_path.exists()
    df = pd.read_csv(out_path)
    assert len(df) == 10
    assert {"time", "streamflow"} <= set(df.columns)
    assert (df["streamflow"] >= 0).all()


def test_detect_outliers_flags_extreme_value():
    """A single extreme value should be flagged as an outlier."""
    series = pd.Series([10, 11, 9, 10, 10, 500])
    flags = detect_outliers(series, n_std=2)
    assert flags.iloc[-1]
    assert not flags.iloc[:-1].any()


def test_detect_outliers_zero_std_returns_all_false():
    """A constant series (zero std) should flag nothing."""
    series = pd.Series([5, 5, 5, 5])
    flags = detect_outliers(series)
    assert not flags.any()
