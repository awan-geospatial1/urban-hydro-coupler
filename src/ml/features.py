"""Feature engineering for the ML flood-risk surrogate model.

Turns a raw Wflow streamflow time-series into a small, fixed-size vector of
hydrologically meaningful summary statistics, so a lightweight regression
model can learn to predict SWMM flooding outcomes without re-running the
full coupled physics-based simulation.
"""
from typing import Dict

import numpy as np
import pandas as pd

#: Canonical, ordered list of feature names. Every dict returned by
#: ``extract_flow_features`` has exactly these keys, and every model in
#: ``src.ml.surrogate`` trains/predicts using this column order.
FEATURE_NAMES = [
    "peak_flow",
    "mean_flow",
    "std_flow",
    "baseflow",
    "total_volume",
    "max_rate_of_rise",
    "time_to_peak_fraction",
    "flashiness_index",
    "pct_time_above_mean",
]


def extract_flow_features(flow: pd.Series) -> Dict[str, float]:
    """Extract a fixed-size feature vector from a streamflow time-series.

    Args:
        flow: Streamflow series, indexed by time (e.g.
            ``HydroCoupler.wflow_flow``). Values are assumed to already be
            cleaned (non-negative, no NaNs) as ``HydroCoupler`` does on load.

    Returns:
        Dict mapping feature name -> value, with keys matching
        ``FEATURE_NAMES``. An empty series returns all zeros.
    """
    if flow.empty:
        return {name: 0.0 for name in FEATURE_NAMES}

    values = flow.to_numpy(dtype=float)
    n = len(values)

    peak_flow = float(values.max())
    mean_flow = float(values.mean())
    std_flow = float(values.std())
    baseflow = float(np.percentile(values, 10))

    # Trapezoidal-rule approximation of total inflow volume over
    # normalized (unitless) time steps. Absolute units depend on the
    # source series' native units and sampling interval, but relative
    # volume is comparable across scenarios sampled at the same interval.
    # np.trapz was removed in NumPy 2.0 in favor of np.trapezoid; fall back
    # for older NumPy versions still pinned by some environments.
    trapezoid = getattr(np, "trapezoid", None) or np.trapz
    total_volume = float(trapezoid(values))

    diffs = np.diff(values)
    max_rate_of_rise = float(diffs.max()) if diffs.size else 0.0

    peak_idx = int(values.argmax())
    time_to_peak_fraction = peak_idx / (n - 1) if n > 1 else 0.0

    # Richards-Baker flashiness index: sum of absolute step-to-step changes
    # divided by total flow. Higher values mean a "flashier" hydrograph
    # (sharp rises/falls), which tends to overwhelm urban drainage capacity
    # faster than the same volume delivered gradually.
    flow_sum = float(values.sum())
    flashiness_index = float(np.abs(diffs).sum()) / flow_sum if flow_sum > 0 else 0.0

    pct_time_above_mean = float((values > mean_flow).mean())

    return {
        "peak_flow": peak_flow,
        "mean_flow": mean_flow,
        "std_flow": std_flow,
        "baseflow": baseflow,
        "total_volume": total_volume,
        "max_rate_of_rise": max_rate_of_rise,
        "time_to_peak_fraction": time_to_peak_fraction,
        "flashiness_index": flashiness_index,
        "pct_time_above_mean": pct_time_above_mean,
    }


def features_to_vector(features: Dict[str, float]) -> np.ndarray:
    """Convert a feature dict into an ordered numpy vector for sklearn.

    Args:
        features: Dict as returned by ``extract_flow_features``.

    Returns:
        1-D array ordered according to ``FEATURE_NAMES``.
    """
    return np.array([features[name] for name in FEATURE_NAMES], dtype=float)
