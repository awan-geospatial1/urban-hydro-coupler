"""AI/ML surrogate modeling for the Urban Hydro-Coupler.

The full ``HydroCoupler`` pipeline (Wflow -> SWMM) is physically accurate
but too slow to run for every scenario in a large ensemble (e.g. hundreds
of downscaled climate futures, or an interactive "what happens if the
storm gets 20% bigger" slider). This package trains a lightweight,
fast machine learning "surrogate" model on the outputs of the physics-based
coupled simulations, and uses it to predict flooding outcomes for new
streamflow scenarios in milliseconds instead of minutes.

It is a *screening* tool, not a replacement for the coupled simulation --
use it to triage which scenarios are worth a full physics-based run.
"""
from src.ml.features import FEATURE_NAMES, extract_flow_features, features_to_vector
from src.ml.surrogate import FloodSurrogateModel

__all__ = [
    "FEATURE_NAMES",
    "extract_flow_features",
    "features_to_vector",
    "FloodSurrogateModel",
]
