from __future__ import annotations
from typing import Any, Dict, Optional
import math
class RouteEvaluator:
    TRAFFIC_THRESHOLDS = (
        (60.0, "low"),
        (40.0, "medium"),
        (25.0, "high"),
    )
    def __init__(self, traffic_engine=None):
        self.traffic_engine = traffic_engine
    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            value = float(value)
            return value if math.isfinite(value) else default
        except (TypeError, ValueError):
            return default
    @staticmethod
    def calculate_eta(distance_km: float, speed_kmh: float) -> float:
        distance = RouteEvaluator._float(distance_km)
        speed = RouteEvaluator._float(speed_kmh)
        if distance < 0:
            raise ValueError("distance_km cannot be negative.")
        if speed <= 0:
            raise ValueError("speed_kmh must be greater than zero.")
        return (distance / speed) * 60.0
    @staticmethod
    def calculate_delay(
        baseline_duration_min: float,
        predicted_duration_min: float,
    ) -> float:
        baseline = max(0.0, RouteEvaluator._float(baseline_duration_min))
        predicted = max(0.0, RouteEvaluator._float(predicted_duration_min))
        return max(0.0, predicted - baseline)
    @classmethod
    def traffic_level(cls, speed_kmh: float) -> str:
        speed = cls._float(speed_kmh)
        for threshold, level in cls.TRAFFIC_THRESHOLDS:
            if speed >= threshold:
                return level
        return "very_high"
    @staticmethod
    def _speeds(prediction: Any) -> list[float]:
        if not isinstance(prediction, dict):
            return []
        values = prediction.get("predicted_speed", [])
        if not isinstance(values, (list, tuple)):
            values = [values]
        return [
            speed
            for value in values
            if (speed := RouteEvaluator._float(value)) > 0
        ]
    @classmethod
    def predicted_speed(cls, prediction: Any) -> Optional[float]:
        speeds = cls._speeds(prediction)
        if not speeds:
            return None
        return sum(speeds) / len(speeds)
    @staticmethod
    def _route_value(route: Dict[str, Any], key: str) -> float:
        return max(0.0, RouteEvaluator._float(route.get(key)))
    @classmethod
    def evaluate_route(
        cls,
        route: Dict[str, Any],
        prediction: Dict[str, Any],
        preference: str = "fastest",
    ) -> Dict[str, Any]:
        if not isinstance(route, dict):
            raise TypeError("route must be a dictionary.")
        if not isinstance(prediction, dict):
            raise TypeError("prediction must be a dictionary.")
        distance_km = cls._route_value(route, "distance_km")
        baseline_duration_min = cls._route_value(route, "duration_min")
        speed_kmh = cls.predicted_speed(prediction)
        if distance_km <= 0:
            raise ValueError("route distance_km must be greater than zero.")
        if speed_kmh is None:
            raise ValueError("prediction contains no positive predicted speed.")
        predicted_duration_min = cls.calculate_eta(
            distance_km,
            speed_kmh,
        )
        delay_minutes = cls.calculate_delay(
            baseline_duration_min,
            predicted_duration_min,
        )
        traffic = cls.traffic_level(speed_kmh)
        return {
            "route_id": route.get("route_id"),
            "distance_km": round(distance_km, 2),
            "baseline_duration_min": round(baseline_duration_min, 2),
            "predicted_speed_kmh": round(speed_kmh, 2),
            "predicted_duration_min": round(predicted_duration_min, 2),
            "delay_minutes": round(delay_minutes, 2),
            "delay_percent": round(
                (delay_minutes / baseline_duration_min) * 100.0,
                2,
            ) if baseline_duration_min > 0 else 0.0,
            "traffic_level": traffic,
            "traffic_horizon_minutes": prediction.get("horizon_minutes"),
            "sensor_indices": prediction.get("sensor_indices", []),
            "preference": preference or "fastest",
        }
    @classmethod
    def evaluate_routes(
        cls,
        routes: list[Dict[str, Any]],
        predictions: list[Dict[str, Any]],
        preference: str = "fastest",
    ) -> list[Dict[str, Any]]:
        if len(routes) != len(predictions):
            raise ValueError("routes and predictions must have the same length.")
        return [
            cls.evaluate_route(route, prediction, preference)
            for route, prediction in zip(routes, predictions)
        ]
