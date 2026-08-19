"""Tests for the ML flood-risk surrogate module (src.ml)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ml.features import FEATURE_NAMES, extract_flow_features, features_to_vector
from src.ml.surrogate import FloodSurrogateModel


@pytest.fixture
def synthetic_flow() -> pd.Series:
    """A small, smoothly-varying synthetic streamflow series."""
    times = pd.date_range("2020-01-01", periods=48, freq="h", tz="UTC")
    values = 5 + 3 * np.sin(np.linspace(0, 4 * np.pi, 48))
    return pd.Series(np.maximum(values, 0), index=times, name="streamflow")


def _make_training_set(n: int = 30, seed: int = 0):
    """Build a small synthetic (features, target) dataset for training tests."""
    rng = np.random.default_rng(seed)
    rows, targets = [], []
    for _ in range(n):
        peak = rng.uniform(1, 50)
        times = pd.date_range("2020-01-01", periods=24, freq="h", tz="UTC")
        flow = pd.Series(np.linspace(1, peak, 24), index=times)
        rows.append(extract_flow_features(flow))
        # Synthetic ground truth loosely correlated with peak flow, so the
        # model has something learnable to fit.
        targets.append(0.01 * peak + rng.normal(0, 0.01))
    return pd.DataFrame(rows), pd.Series(targets)


class TestExtractFlowFeatures:
    def test_returns_all_expected_keys(self, synthetic_flow):
        features = extract_flow_features(synthetic_flow)
        assert set(features.keys()) == set(FEATURE_NAMES)
        assert all(np.isfinite(v) for v in features.values())

    def test_empty_series_returns_zeros(self):
        features = extract_flow_features(pd.Series(dtype=float))
        assert all(v == 0.0 for v in features.values())

    def test_peak_flow_matches_max(self, synthetic_flow):
        features = extract_flow_features(synthetic_flow)
        assert features["peak_flow"] == pytest.approx(synthetic_flow.max())

    def test_flashiness_index_is_zero_for_constant_flow(self):
        times = pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC")
        flow = pd.Series([5.0] * 10, index=times)
        features = extract_flow_features(flow)
        assert features["flashiness_index"] == pytest.approx(0.0)
        assert features["max_rate_of_rise"] == pytest.approx(0.0)


def test_features_to_vector_order_matches_feature_names(synthetic_flow):
    features = extract_flow_features(synthetic_flow)
    vector = features_to_vector(features)
    assert vector.shape == (len(FEATURE_NAMES),)
    assert vector[0] == features[FEATURE_NAMES[0]]


class TestFloodSurrogateModel:
    def test_train_raises_with_too_few_samples(self):
        model = FloodSurrogateModel()
        features, target = _make_training_set(n=3)
        with pytest.raises(ValueError):
            model.train(features, target)

    def test_train_and_predict_roundtrip(self):
        model = FloodSurrogateModel()
        features, target = _make_training_set(n=30)
        metrics = model.train(features, target)
        assert set(metrics) >= {"mae", "rmse", "r2", "n_train", "n_val"}

        preds = model.predict(features.iloc[:5])
        assert preds.shape == (5,)

    def test_predict_before_train_raises(self):
        model = FloodSurrogateModel()
        with pytest.raises(RuntimeError):
            model.predict(pd.DataFrame([{name: 0.0 for name in FEATURE_NAMES}]))

    def test_predict_from_series_before_train_raises(self, synthetic_flow):
        model = FloodSurrogateModel()
        with pytest.raises(RuntimeError):
            model.predict_from_series(synthetic_flow)

    def test_predict_from_series_returns_risk_level(self, synthetic_flow):
        model = FloodSurrogateModel()
        features, target = _make_training_set(n=30)
        model.train(features, target)

        result = model.predict_from_series(synthetic_flow)
        assert "predicted_max_depth" in result
        assert isinstance(result["predicted_max_depth"], float)
        assert result["risk_level"] in {"low", "medium", "high"}
        assert set(result["features"].keys()) == set(FEATURE_NAMES)

    def test_save_without_training_raises(self, tmp_path: Path):
        model = FloodSurrogateModel()
        with pytest.raises(RuntimeError):
            model.save(tmp_path / "surrogate.joblib")

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        model = FloodSurrogateModel()
        features, target = _make_training_set(n=30)
        model.train(features, target)

        save_path = tmp_path / "nested" / "surrogate.joblib"
        model.save(save_path)
        assert save_path.exists()

        loaded = FloodSurrogateModel.load(save_path)
        preds_original = model.predict(features.iloc[:5])
        preds_loaded = loaded.predict(features.iloc[:5])
        np.testing.assert_allclose(preds_original, preds_loaded)
        assert loaded.metrics_ == model.metrics_

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            FloodSurrogateModel.load(tmp_path / "does_not_exist.joblib")
