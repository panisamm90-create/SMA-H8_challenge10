from pathlib import Path
import joblib
import numpy as np
from backend.ml.inference_features import (
    build_inference_features,
    FINAL_FEATURES,
)
class TrafficEngine:
    ET_WEIGHT = 0.50
    HGB_WEIGHT = 0.50
    PREDICTION_HORIZON_MINUTES = 15
    def __init__(
        self,
        model_dir=None,
        speed_matrix=None,
        neighbor_mean=None,
        neighbor_lag1=None,
        neighbor_lag3=None,
        neighbor_change=None,
        neighbor_std=None,
        temperature=None,
        humidity=None,
        rain=None,
        weather_code=None,
        hour=None,
        minute=None,
    ):
        if model_dir is None:
            candidates = (
                Path(__file__).resolve().parent / "models",
                Path(__file__).resolve().parents[1] / "models",
                Path.cwd() / "models",
                Path.cwd() / "backend" / "models",
            )
            model_dir = next(
                (
                    path
                    for path in candidates
                    if (
                        path / "extra_trees_spatial.joblib"
                    ).exists()
                    and (
                        path / "hgb_spatial.joblib"
                    ).exists()
                ),
                candidates[0],
            )
        model_dir = Path(model_dir)
        self.extra_trees = joblib.load(
            model_dir
            / "extra_trees_spatial.joblib"
        )
        self.hgb = joblib.load(
            model_dir
            / "hgb_spatial.joblib"
        )
        self.speed_matrix = speed_matrix
        self.neighbor_mean = neighbor_mean
        self.neighbor_lag1 = neighbor_lag1
        self.neighbor_lag3 = neighbor_lag3
        self.neighbor_change = neighbor_change
        self.neighbor_std = neighbor_std
        self.temperature = temperature
        self.humidity = humidity
        self.rain = rain
        self.weather_code = weather_code
        self.hour = hour
        self.minute = minute
        if self.extra_trees.n_features_in_ != 28:
            raise ValueError(
                "Extra Trees expects "
                f"{self.extra_trees.n_features_in_} features, "
                "expected 28."
            )
        if self.hgb.n_features_in_ != 28:
            raise ValueError(
                "HGB expects "
                f"{self.hgb.n_features_in_} features, "
                "expected 28."
            )
    def predict(
        self,
        time_index,
        sensor_indices,
    ):
        if self.speed_matrix is None:
            raise ValueError(
                "speed_matrix is not configured."
            )
        sensor_indices = np.asarray(
            sensor_indices,
            dtype=np.int32
        )
        if time_index < 24:
            raise ValueError(
                "At least 24 historical timesteps "
                "are required."
            )
        X = build_inference_features(
            time_index=time_index,
            sensor_indices=sensor_indices,
            speed_matrix=self.speed_matrix,
            temperature=self.temperature,
            humidity=self.humidity,
            rain=self.rain,
            weather_code=self.weather_code,
            hour=self.hour,
            minute=self.minute,
            neighbor_mean=self.neighbor_mean,
            neighbor_lag1=self.neighbor_lag1,
            neighbor_lag3=self.neighbor_lag3,
            neighbor_change=self.neighbor_change,
            neighbor_std=self.neighbor_std,
        )
        if X.shape[1] != 28:
            raise RuntimeError(
                f"Invalid feature shape: {X.shape}"
            )
        if not np.isfinite(X).all():
            raise RuntimeError(
                "Inference features contain "
                "NaN or Inf."
            )
        pred_et = (
            self.extra_trees
            .predict(X)
        )
        pred_hgb = (
            self.hgb
            .predict(X)
        )
        prediction = (
            self.ET_WEIGHT * pred_et
            +
            self.HGB_WEIGHT * pred_hgb
        )
        prediction = prediction.astype(
            np.float32
        )
        return {
            "horizon_minutes":
                self.PREDICTION_HORIZON_MINUTES,
            "sensor_indices":
                sensor_indices.tolist(),
            "predicted_speed":
                prediction.tolist(),
            "extra_trees_prediction":
                pred_et.astype(
                    np.float32
                ).tolist(),
            "hgb_prediction":
                pred_hgb.astype(
                    np.float32
                ).tolist(),
            "ensemble_weight": {
                "extra_trees":
                    self.ET_WEIGHT,
                "hgb":
                    self.HGB_WEIGHT,
            },
            "feature_count":
                X.shape[1],
        }