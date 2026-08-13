"""Utility functions for the Urban Hydro-Coupler."""
import json
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import yaml


def load_config(config_path: Union[str, Path]) -> dict:
    """Load configuration from a YAML or JSON file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Parsed configuration parameters.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the extension isn't ``.yaml``/``.yml``/``.json``.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        if config_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        if config_path.suffix == ".json":
            return json.load(f)
        raise ValueError(f"Unsupported config format: {config_path.suffix}")


def validate_timezone(df: pd.DataFrame, time_column: str = "time") -> pd.DataFrame:
    """Ensure a DataFrame's time column is timezone-aware (UTC).

    Timezone bugs are a common source of significant errors in hydrological
    modeling, so this normalizes any naive or non-UTC column to UTC.

    Args:
        df: DataFrame containing a time column.
        time_column: Name of the time column.

    Returns:
        The same DataFrame with the time column converted to UTC.

    Raises:
        ValueError: If ``time_column`` isn't present in ``df``.
    """
    if time_column not in df.columns:
        raise ValueError(f"Column '{time_column}' not found in DataFrame")

    if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
        df[time_column] = pd.to_datetime(df[time_column])

    if df[time_column].dt.tz is None:
        df[time_column] = df[time_column].dt.tz_localize("UTC")
    else:
        df[time_column] = df[time_column].dt.tz_convert("UTC")

    return df


def create_sample_wflow_output(
    output_path: Path,
    start_date: str = "2020-01-01",
    days: int = 365,
    mean_flow: float = 10.0,
    seed: Optional[int] = 42,
) -> None:
    """Create a sample Wflow output CSV for testing and demos.

    Args:
        output_path: Where to save the CSV.
        start_date: Start date for the time-series.
        days: Number of daily steps to generate.
        mean_flow: Mean streamflow value.
        seed: Random seed for reproducibility (``None`` for non-deterministic).
    """
    rng = np.random.default_rng(seed)

    dates = pd.date_range(start=start_date, periods=days, freq="D", tz="UTC")
    seasonal = 5 * np.sin(2 * np.pi * np.arange(days) / 365)
    noise = 2 * rng.standard_normal(days)
    flows = np.maximum(0, mean_flow + seasonal + noise)

    df = pd.DataFrame({"time": dates, "streamflow": flows})
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Sample Wflow output saved to: {output_path}")


def detect_outliers(series: pd.Series, n_std: float = 3.0) -> pd.Series:
    """Flag values more than ``n_std`` standard deviations from the mean.

    Args:
        series: Numeric series to check.
        n_std: Number of standard deviations to use as the threshold.

    Returns:
        Boolean mask, ``True`` where a value is flagged as an outlier.
    """
    mean = series.mean()
    std = series.std()
    if std == 0 or np.isnan(std):
        return pd.Series(False, index=series.index)
    return (series - mean).abs() > (n_std * std)
