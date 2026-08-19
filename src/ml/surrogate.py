"""ML surrogate model for rapid urban flood-risk screening.

Running the full coupled Wflow -> SWMM simulation (``HydroCoupler``) is
accurate but slow, which makes it impractical to screen large scenario
ensembles -- e.g. hundreds of CMIP6-downscaled climate futures, or an
interactive "what if the storm is 20% bigger" control in a dashboard.

This module trains a lightweight gradient-boosted regression model that
learns the mapping from streamflow-hydrograph features (see
``src.ml.features``) to the coupled model's peak node depth, so new
scenarios can be screened in milliseconds instead of minutes. It is a
*screening* tool: any scenario it flags as medium/high risk should still be
confirmed with a full ``HydroCoupler.run_coupled_simulation()`` run.
"""
import logging
from pathlib import Path
from typing import Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split

from src.ml.features import FEATURE_NAMES, extract_flow_features, features_to_vector

logger = logging.getLogger(__name__)

#: Coarse risk buckets derived from predicted peak depth (in the SWMM
#: model's native depth units, e.g. meters or feet). These are reasonable
#: generic defaults -- tune per-catchment once real training data and
#: known flood thresholds for your SWMM model are available.
RISK_THRESHOLDS = {"low": 0.0, "medium": 0.3, "high": 0.6}


class FloodSurrogateModel:
    """Gradient-boosted regression surrogate for peak SWMM node depth.

    Example:
        >>> model = FloodSurrogateModel()
        >>> model.train(feature_rows, targets)  # doctest: +SKIP
        >>> model.predict_from_series(wflow_series)  # doctest: +SKIP
        {'predicted_max_depth': 0.42, 'risk_level': 'medium', 'features': {...}}
    """

    def __init__(self, model: GradientBoostingRegressor = None):
        """Initialize the surrogate.

        Args:
            model: An already-trained sklearn regressor to wrap (used by
                ``load``). If omitted, a fresh untrained
                ``GradientBoostingRegressor`` is created.
        """
        self.model = model if model is not None else GradientBoostingRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
        )
        self._is_trained = model is not None
        self.metrics_: Dict[str, float] = {}

    def train(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Dict[str, float]:
        """Train the surrogate on (hydrograph features, peak depth) pairs.

        Args:
            features: DataFrame with (at least) columns ``FEATURE_NAMES``,
                one row per training scenario -- typically the output of
                ``extract_flow_features`` for each scenario's Wflow series.
            target: Series of the physics-based coupled model's peak node
                depth (``flooding_summary["max_depth"]``) for each row of
                ``features``.
            test_size: Fraction of rows held out for validation.
            random_state: Seed for the train/validation split.

        Returns:
            Dict of hold-out validation metrics: ``mae``, ``rmse``, ``r2``,
            ``n_train``, ``n_val``.

        Raises:
            ValueError: If fewer than 5 training samples are provided.
        """
        if len(features) < 5:
            raise ValueError(
                f"Need at least 5 training samples, got {len(features)}. "
                "Run more coupled simulations first -- see "
                "scripts/train_surrogate.py."
            )

        X = features[FEATURE_NAMES].to_numpy(dtype=float)
        y = target.to_numpy(dtype=float)

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        self.model.fit(X_train, y_train)
        self._is_trained = True

        preds = self.model.predict(X_val)
        mae = float(np.mean(np.abs(preds - y_val)))
        rmse = float(np.sqrt(np.mean((preds - y_val) ** 2)))
        ss_res = float(np.sum((y_val - preds) ** 2))
        ss_tot = float(np.sum((y_val - y_val.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        self.metrics_ = {
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "n_train": len(X_train),
            "n_val": len(X_val),
        }
        logger.info("Surrogate trained. Validation metrics: %s", self.metrics_)
        return self.metrics_

    def predict(self, feature_rows: pd.DataFrame) -> np.ndarray:
        """Predict peak node depth for one or more feature rows.

        Args:
            feature_rows: DataFrame with columns ``FEATURE_NAMES``.

        Returns:
            Array of predicted peak depths, one per row.

        Raises:
            RuntimeError: If the model hasn't been trained or loaded yet.
        """
        if not self._is_trained:
            raise RuntimeError("Model has not been trained or loaded yet.")
        X = feature_rows[FEATURE_NAMES].to_numpy(dtype=float)
        return self.model.predict(X)

    def predict_from_series(self, flow: pd.Series) -> Dict[str, object]:
        """Predict a flooding outcome directly from a raw streamflow series.

        Convenience wrapper that extracts features and predicts in one
        step -- this is what the API's ``/predict`` endpoint and the
        dashboard's "AI Flood Risk Screening" panel call.

        Args:
            flow: Streamflow time-series (e.g. ``HydroCoupler.wflow_flow``).

        Returns:
            Dict with ``predicted_max_depth`` (float), ``risk_level``
            (``"low"``/``"medium"``/``"high"``), and the extracted
            ``features`` dict used for the prediction.

        Raises:
            RuntimeError: If the model hasn't been trained or loaded yet.
        """
        if not self._is_trained:
            raise RuntimeError("Model has not been trained or loaded yet.")

        features = extract_flow_features(flow)
        vector = features_to_vector(features).reshape(1, -1)
        predicted = float(self.model.predict(vector)[0])

        return {
            "predicted_max_depth": predicted,
            "risk_level": self._risk_level(predicted),
            "features": features,
        }

    @staticmethod
    def _risk_level(predicted_depth: float) -> str:
        """Bucket a predicted depth into a coarse risk label."""
        if predicted_depth >= RISK_THRESHOLDS["high"]:
            return "high"
        if predicted_depth >= RISK_THRESHOLDS["medium"]:
            return "medium"
        return "low"

    def save(self, path: Path) -> None:
        """Persist the trained model and its validation metrics to disk.

        Args:
            path: Destination ``.joblib`` file. Parent dirs are created.

        Raises:
            RuntimeError: If the model hasn't been trained yet.
        """
        if not self._is_trained:
            raise RuntimeError("Cannot save an untrained model.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self.model, "metrics": self.metrics_, "feature_names": FEATURE_NAMES},
            path,
        )
        logger.info("Surrogate model saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> "FloodSurrogateModel":
        """Load a previously trained surrogate model from disk.

        Args:
            path: Path to a ``.joblib`` file written by ``save``.

        Returns:
            A ready-to-predict ``FloodSurrogateModel``.

        Raises:
            FileNotFoundError: If ``path`` doesn't exist.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Surrogate model not found at {path}")
        payload = joblib.load(path)
        instance = cls(model=payload["model"])
        instance.metrics_ = payload.get("metrics", {})
        return instance
