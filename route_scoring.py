from __future__ import annotations
from typing import Any, Dict, List, Optional
class RouteScoringEngine:
    DEFAULT_FUEL_CONSUMPTION_L_PER_100KM = 8.0
    GASOLINE_CO2_KG_PER_LITER = 2.31
    DEFAULT_WEIGHTS = {
        "time": 0.45,
        "traffic": 0.30,
        "weather": 0.10,
        "events": 0.10,
        "accident": 0.05,
    }
    PREFERENCE_WEIGHTS = {
        "fastest": {
            "time": 0.65,
            "traffic": 0.20,
            "weather": 0.05,
            "events": 0.05,
            "accident": 0.05,
        },
        "least_traffic": {
            "time": 0.15,
            "traffic": 0.65,
            "weather": 0.05,
            "events": 0.10,
            "accident": 0.05,
        },
        "economical": {
            "time": 0.20,
            "traffic": 0.25,
            "weather": 0.10,
            "events": 0.10,
            "accident": 0.05,
            "distance": 0.30,
        },
        "eco": {
            "time": 0.15,
            "traffic": 0.20,
            "weather": 0.05,
            "events": 0.05,
            "accident": 0.05,
            "distance": 0.50,
        },
    }
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = self._normalize_weights(
            weights or self.DEFAULT_WEIGHTS
        )
    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
            return number if number == number else default
        except (TypeError, ValueError):
            return default
    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
    @classmethod
    def _normalize_weights(cls, weights: Dict[str, float]) -> Dict[str, float]:
        keys = ("time", "traffic", "weather", "events", "accident", "distance")
        result = {
            key: max(0.0, cls._float(weights.get(key)))
            for key in keys
        }
        total = sum(result.values())
        if total <= 0:
            return {"time": 1.0, "traffic": 0.0, "weather": 0.0,
                    "events": 0.0, "accident": 0.0, "distance": 0.0}
        return {key: value / total for key, value in result.items()}
    @classmethod
    def _context(cls, value: Any, index: int) -> Any:
        if isinstance(value, list):
            return value[index] if index < len(value) else None
        return value
    @classmethod
    def _traffic_score(cls, traffic: Any) -> float:
        if not isinstance(traffic, dict):
            return 0.0
        values = traffic.get("predicted_speed", [])
        if not isinstance(values, (list, tuple)):
            values = [values]
        speeds = [
            cls._float(value)
            for value in values
            if cls._float(value) > 0
        ]
        if not speeds:
            return 0.0
        average = sum(speeds) / len(speeds)
        return cls._clamp((60.0 - average) / 50.0)
    @classmethod
    def _average_predicted_speed(cls, traffic: Any) -> Optional[float]:
        if not isinstance(traffic, dict):
            return None
        values = traffic.get("predicted_speed", [])
        if not isinstance(values, (list, tuple)):
            values = [values]
        speeds = [
            cls._float(value)
            for value in values
            if cls._float(value) > 0
        ]
        if not speeds:
            return None
        return sum(speeds) / len(speeds)
    @classmethod
    def _weather_score(cls, weather: Any) -> float:
        if not isinstance(weather, dict):
            return 0.0
        data = weather.get("departure", weather)
        if not isinstance(data, dict):
            return 0.0
        rain = max(0.0, cls._float(data.get("rain")))
        code = cls._float(data.get("weather_code"))
        rain_score = cls._clamp(rain / 10.0)
        severe_score = 1.0 if code >= 95 else 0.75 if code >= 80 else 0.5 if code >= 60 else 0.3 if code >= 50 else 0.0
        return max(rain_score, severe_score)
    @classmethod
    def _events_score(cls, events: Any) -> float:
        if events is None:
            return 0.0
        if isinstance(events, dict):
            if "event_score" in events:
                return cls._clamp(cls._float(events["event_score"]))
            value = events.get("event_count")
            if value is None:
                items = events.get("events", [])
                value = len(items) if isinstance(items, list) else 0
            count = cls._float(value)
        elif isinstance(events, list):
            count = float(len(events))
        else:
            return 0.0
        return cls._clamp(count / 5.0)
    @classmethod
    def _accident_score(cls, accident: Any) -> float:
        if accident is None:
            return 0.0
        if isinstance(accident, (int, float)):
            return cls._clamp(cls._float(accident))
        if not isinstance(accident, dict):
            return 0.0
        for key in ("accident_risk", "risk", "score", "probability"):
            if key in accident:
                value = cls._float(accident[key])
                if 1.0 < value <= 100.0:
                    value /= 100.0
                return cls._clamp(value)
        return 0.0
    @classmethod
    def _duration(cls, route: Dict[str, Any]) -> float:
        duration = cls._float(route.get("duration_min"))
        if duration > 0:
            return duration
        return max(0.0, cls._float(route.get("duration")) / 60.0)
    @classmethod
    def _distance(cls, route: Dict[str, Any]) -> float:
        distance = cls._float(route.get("distance_km"))
        if distance > 0:
            return distance
        return max(0.0, cls._float(route.get("distance")) / 1000.0)
    @classmethod
    def _preference(cls, preference: str) -> str:
        value = (preference or "fastest").strip().lower()
        aliases = {
            "quickest": "fastest",
            "least traffic": "least_traffic",
            "low traffic": "least_traffic",
            "eco-friendly": "eco",
            "eco_friendly": "eco",
            "economic": "economical",
        }
        return aliases.get(value, value)
    def _weights_for(self, preference: str) -> Dict[str, float]:
        selected = self.PREFERENCE_WEIGHTS.get(
            self._preference(preference),
            self.DEFAULT_WEIGHTS,
        )
        return self._normalize_weights(selected)
    @classmethod
    def _fuel_consumption_l_per_100km(cls, route: Dict[str, Any]) -> float:
        value = cls._float(
            route.get("fuel_consumption_l_per_100km"),
            cls.DEFAULT_FUEL_CONSUMPTION_L_PER_100KM,
        )
        return value if value > 0 else cls.DEFAULT_FUEL_CONSUMPTION_L_PER_100KM
    @classmethod
    def _fuel_estimate(cls, distance_km: float, route: Dict[str, Any]) -> Dict[str, float]:
        consumption = cls._fuel_consumption_l_per_100km(route)
        liters = max(0.0, distance_km) * consumption / 100.0
        co2_kg = liters * cls.GASOLINE_CO2_KG_PER_LITER
        return {
            "fuel_consumption_l_per_100km": round(consumption, 2),
            "estimated_fuel_l": round(liters, 3),
            "estimated_co2_kg": round(co2_kg, 3),
            "co2_factor_kg_per_liter": cls.GASOLINE_CO2_KG_PER_LITER,
            "estimation_basis": "distance × vehicle fuel-consumption assumption",
        }
    def score_route(
        self,
        route: Dict[str, Any],
        traffic: Any = None,
        weather: Any = None,
        events: Any = None,
        accident: Any = None,
        reference_duration_minutes: Optional[float] = None,
        reference_distance_km: Optional[float] = None,
        preference: str = "fastest",
    ) -> Dict[str, Any]:
        baseline_duration = self._duration(route)
        distance = self._distance(route)
        predicted_speed_value = self._average_predicted_speed(traffic)
        predicted_speed = predicted_speed_value or 0.0
        realtime = traffic.get("realtime") if isinstance(traffic, dict) else None
        realtime_ratio = None
        if isinstance(realtime, dict):
            try:
                value = float(realtime.get("congestion_ratio"))
                if value == value:
                    realtime_ratio = max(0.0, min(0.85, value))
            except (TypeError, ValueError):
                realtime_ratio = None
        if realtime_ratio is not None and baseline_duration > 0:
            predicted_duration = baseline_duration / max(0.15, 1.0 - realtime_ratio)
            predicted_speed = (
                (distance / predicted_duration) * 60.0
                if distance > 0 and predicted_duration > 0
                else predicted_speed
            )
        else:
            predicted_duration = (
                (distance / predicted_speed) * 60.0
                if distance > 0 and predicted_speed > 0
                else baseline_duration
            )
        duration = predicted_duration
        if reference_duration_minutes is None:
            reference_duration_minutes = duration
        if reference_distance_km is None:
            reference_distance_km = distance
        time_score = (
            max(0.0, duration - reference_duration_minutes) / 30.0
            if reference_duration_minutes > 0
            else 0.0
        )
        distance_score = (
            max(0.0, distance - reference_distance_km) / 20.0
            if reference_distance_km > 0
            else 0.0
        )
        components = {
            "time": self._clamp(time_score),
            "traffic": self._traffic_score(traffic),
            "weather": self._weather_score(weather),
            "events": self._events_score(events),
            "accident": self._accident_score(accident),
            "distance": self._clamp(distance_score),
        }
        weights = self._weights_for(preference)
        score = sum(
            components[key] * weights.get(key, 0.0)
            for key in components
        )
        score = self._clamp(score)
        normalized_preference = self._preference(preference)
        return {
            "score": round(score, 4),
            "score_100": round((1.0 - score) * 100.0, 2),
            "components": {
                key: round(value, 4)
                for key, value in components.items()
            },
            "weights": weights,
            "baseline_duration_min": round(baseline_duration, 2),
            "predicted_duration_min": round(predicted_duration, 2),
            "delay_minutes": round(max(0.0, predicted_duration - baseline_duration), 2),
            "predicted_speed_kmh": round(predicted_speed, 2) if predicted_speed > 0 else None,
            "traffic_score": round(components["traffic"], 4),
            "realtime_congestion_ratio": round(realtime_ratio, 4) if realtime_ratio is not None else None,
            "realtime_duration_multiplier": (
                round(1.0 / max(0.15, 1.0 - realtime_ratio), 4)
                if realtime_ratio is not None else None
            ),
            "traffic_level": (
                "Light" if predicted_speed >= 55
                else "Moderate" if predicted_speed >= 35
                else "Heavy" if predicted_speed >= 20
                else "Severe" if predicted_speed > 0
                else "Unavailable"
            ),
            "distance_km": round(distance, 2),
            "fuel": self._fuel_estimate(distance, route),
            "estimated_fuel_l": self._fuel_estimate(distance, route)["estimated_fuel_l"],
            "estimated_co2_kg": self._fuel_estimate(distance, route)["estimated_co2_kg"],
            "preference": normalized_preference,
            "explanation": self._explanation(components),
            "selection_mode": normalized_preference,
            "eco": {
                "enabled": normalized_preference == "eco",
                "distance_priority": normalized_preference == "eco",
            },
        }
    @staticmethod
    def _explanation(components: Dict[str, float]) -> List[str]:
        reasons = []
        if components["traffic"] >= 0.65:
            reasons.append("High traffic impact")
        elif components["traffic"] >= 0.35:
            reasons.append("Moderate traffic impact")
        else:
            reasons.append("Traffic conditions are favorable")
        if components["time"] >= 0.35:
            reasons.append("Longer travel time than the fastest option")
        if components["distance"] >= 0.35:
            reasons.append("Longer route distance")
        if components["weather"] >= 0.5:
            reasons.append("Weather may affect travel")
        if components["events"] >= 0.5:
            reasons.append("Events may increase congestion")
        if components["accident"] >= 0.5:
            reasons.append("Elevated accident risk")
        return reasons
    def rank_routes(
        self,
        routes: Any,
        traffic: Any = None,
        weather: Any = None,
        events: Any = None,
        accident: Any = None,
        preference: str = "fastest",
    ) -> Dict[str, Any]:
        if isinstance(routes, dict):
            routes = routes.get("routes", [routes])
        if not isinstance(routes, list) or not routes:
            return {
                "routes": [],
                "ranked_routes": [],
                "best_route": None,
                "best_route_id": None,
                "route_count": 0,
                "preference": self._preference(preference),
            }
        durations = [self._duration(route) for route in routes]
        distances = [self._distance(route) for route in routes]
        valid_durations = [value for value in durations if value > 0]
        valid_distances = [value for value in distances if value > 0]
        reference_duration = min(valid_durations) if valid_durations else 0.0
        reference_distance = min(valid_distances) if valid_distances else 0.0
        results = []
        for index, route in enumerate(routes):
            scored = self.score_route(
                route=route,
                traffic=self._context(traffic, index),
                weather=self._context(weather, index),
                events=self._context(events, index),
                accident=self._context(accident, index),
                reference_duration_minutes=reference_duration,
                reference_distance_km=reference_distance,
                preference=preference,
            )
            scored["route_id"] = route.get("route_id", index + 1)
            if self._preference(preference) == "eco":
                scored["eco_score"] = round(
                    (self._distance(route) / reference_distance)
                    if reference_distance > 0
                    else 0.0,
                    4,
                )
                scored["eco_priority"] = "distance_first"
            results.append(scored)
        normalized_preference = self._preference(preference)
        if normalized_preference == "least_traffic":
            results.sort(
                key=lambda item: (
                    item.get("traffic_score", 1.0),
                    item.get("score", 1.0),
                    item.get("predicted_duration_min", float("inf")),
                )
            )
        else:
            results.sort(
                key=lambda item: (
                    item.get("score", 1.0),
                    item.get("predicted_duration_min", float("inf")),
                )
            )
        for rank, result in enumerate(results, 1):
            result["rank"] = rank
            result["recommended"] = rank == 1
        best = results[0]
        return {
            "routes": results,
            "ranked_routes": results,
            "best_route": best,
            "best_route_id": best["route_id"],
            "route_count": len(results),
            "preference": self._preference(preference),
            "eco_mode": self._preference(preference) == "eco",
        }
    def score_context(self, context: Dict[str, Any], preference: str = "fastest") -> Dict[str, Any]:
        if not isinstance(context, dict):
            raise TypeError("context must be a dictionary.")
        return self.rank_routes(
            routes=context.get("route", context.get("routes")),
            traffic=context.get("traffic"),
            weather=context.get("weather"),
            events=context.get("events"),
            accident=context.get("accident"),
            preference=preference,
        )
    def get_best_route(self, context: Dict[str, Any], preference: str = "fastest"):
        return self.score_context(context, preference)["best_route"]
def score_routes(
    routes: Any,
    traffic: Any = None,
    weather: Any = None,
    events: Any = None,
    accident: Any = None,
    preference: str = "fastest",
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    engine = RouteScoringEngine(weights=weights)
    return engine.rank_routes(
        routes=routes,
        traffic=traffic,
        weather=weather,
        events=events,
        accident=accident,
        preference=preference,
    )
