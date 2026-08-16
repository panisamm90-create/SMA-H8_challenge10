
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import requests
from dotenv import load_dotenv
def _load_project_env() -> None:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")


_load_project_env()
class TomTomRealtimeTrafficProvider:
    BASE_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData"
    DEFAULT_ZOOM = 14
    DEFAULT_TIMEOUT = 8
    DEFAULT_SAMPLE_POINTS = 8
    DEFAULT_CACHE_SECONDS = 45
    def __init__(
        self,
        api_key: Optional[str] = None,
        zoom: int = DEFAULT_ZOOM,
        timeout: int = DEFAULT_TIMEOUT,
        sample_points: int = DEFAULT_SAMPLE_POINTS,
        cache_seconds: int = DEFAULT_CACHE_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = (api_key or os.getenv("TOMTOM_API_KEY", "")).strip()
        self.zoom = int(zoom)
        self.timeout = int(timeout)
        self.sample_points = max(1, int(sample_points))
        self.cache_seconds = max(0, int(cache_seconds))
        self.session = session or requests.Session()
        self._cache: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}
    @property
    def enabled(self) -> bool:
        return bool(self.api_key)
    @staticmethod
    def _route_coordinates(route: Dict[str, Any]) -> List[Tuple[float, float]]:
        geometry = route.get("geometry", {}) if isinstance(route, dict) else {}
        coordinates = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
        result: List[Tuple[float, float]] = []
        for point in coordinates:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                lon, lat = float(point[0]), float(point[1])
            except (TypeError, ValueError):
                continue
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                result.append((lon, lat))
        return result
    @staticmethod
    def _sample_coordinates(
        coordinates: Sequence[Tuple[float, float]],
        count: int,
    ) -> List[Tuple[float, float]]:
        if not coordinates:
            return []
        if len(coordinates) <= count:
            return list(coordinates)
        indices = [round(i * (len(coordinates) - 1) / (count - 1)) for i in range(count)]
        return [coordinates[i] for i in sorted(set(indices))]
    def get_point_traffic(
        self,
        latitude: float,
        longitude: float,
    ) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "TOMTOM_API_KEY is not configured. "
                "Expected it in the project root .env file."
            )
        lat = round(float(latitude), 5)
        lon = round(float(longitude), 5)
        cache_key = (lat, lon)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] <= self.cache_seconds:
            return dict(cached[1])
        params = {
            "key": self.api_key,
            "point": f"{lat},{lon}",
            "unit": "kmph",
        }
        url = f"{self.BASE_URL}/absolute/{self.zoom}/json"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        flow = payload.get("flowSegmentData") or {}
        result = {
            "latitude": lat,
            "longitude": lon,
            "current_speed_kmh": self._number(flow.get("currentSpeed")),
            "free_flow_speed_kmh": self._number(flow.get("freeFlowSpeed")),
            "current_travel_time_s": self._number(flow.get("currentTravelTime")),
            "free_flow_travel_time_s": self._number(flow.get("freeFlowTravelTime")),
            "confidence": self._number(flow.get("confidence")),
            "road_closure": bool(flow.get("roadClosure", False)),
            "frc": flow.get("frc"),
            "coordinates": flow.get("coordinates", {}),
        }
        if result["current_speed_kmh"] is None:
            raise RuntimeError("TomTom returned no currentSpeed for the sampled road segment.")
        self._cache[cache_key] = (now, result)
        return dict(result)
    def get_route_traffic(
        self,
        route: Dict[str, Any],
        sample_points: Optional[int] = None,
    ) -> Dict[str, Any]:
        coordinates = self._route_coordinates(route)
        samples = self._sample_coordinates(
            coordinates,
            max(1, int(sample_points or self.sample_points)),
        )
        if not samples:
            raise ValueError("Route geometry contains no valid coordinates.")
        observations: List[Dict[str, Any]] = []
        errors: List[str] = []
        for lon, lat in samples:
            try:
                observations.append(self.get_point_traffic(lat, lon))
            except Exception as error:
                errors.append(str(error))
        speeds = [
            float(item["current_speed_kmh"])
            for item in observations
            if item.get("current_speed_kmh") is not None
            and float(item["current_speed_kmh"]) > 0
        ]
        free_flow = [
            float(item["free_flow_speed_kmh"])
            for item in observations
            if item.get("free_flow_speed_kmh") is not None
            and float(item["free_flow_speed_kmh"]) > 0
        ]
        confidences = [
            float(item["confidence"])
            for item in observations
            if item.get("confidence") is not None
        ]
        if not speeds:
            raise RuntimeError(
                "TomTom returned no usable traffic observations. "
                + (errors[0] if errors else "")
            )
        import statistics
        current_speed = statistics.median(speeds)
        free_flow_speed = statistics.median(free_flow) if free_flow else None
        confidence = statistics.median(confidences) if confidences else None
        closure = any(bool(item.get("road_closure")) for item in observations)
        ratios = []
        for item in observations:
            cur = item.get("current_speed_kmh")
            ff = item.get("free_flow_speed_kmh")
            if cur is None or ff is None or float(ff) <= 0:
                continue
            ratios.append(max(0.0, min(1.0, 1.0 - float(cur) / float(ff))))
        congestion_ratio = statistics.median(ratios) if ratios else None
        return {
            "source": "tomtom",
            "live": True,
            "sample_count": len(observations),
            "current_speed_kmh": round(current_speed, 2),
            "free_flow_speed_kmh": round(free_flow_speed, 2) if free_flow_speed is not None else None,
            "confidence": round(confidence, 4) if confidence is not None else None,
            "congestion_ratio": round(congestion_ratio, 4) if congestion_ratio is not None else None,
            "road_closure": closure,
            "observations": observations,
            "errors": errors[:3],
            "timestamp": time.time(),
        }
    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None
