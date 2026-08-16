from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple
import joblib
import numpy as np
import pandas as pd
class AccidentEngine:
   
    FEATURES = [
        "Start_Lat",
        "Start_Lng",
        "Temperature(F)",
        "Humidity(%)",
        "Pressure(in)",
        "Visibility(mi)",
        "Wind_Speed(mph)",
        "Precipitation(in)",
        "Weather_Condition",
        "Junction",
        "Crossing",
        "Traffic_Signal",
        "Stop",
        "Railway",
        "Roundabout",
        "Bump",
        "Traffic_Calming",
    ]
    BOOL_FEATURES = [
        "Junction",
        "Crossing",
        "Traffic_Signal",
        "Stop",
        "Railway",
        "Roundabout",
        "Bump",
        "Traffic_Calming",
    ]
    def __init__(
        self,
        model_path: Optional[str | Path] = None,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.model_path = Path(
            model_path
            or project_root / "backend" / "engines" / "models" / "accident_model.joblib"
        )
        if not self.model_path.exists():
            raise FileNotFoundError(
                "Accident model not found:\n"
                f"{self.model_path}\n\n"
                "Run the final US_Accident_prediction notebook first."
            )
        bundle = joblib.load(self.model_path)
        if not isinstance(bundle, dict) or "model" not in bundle:
            raise RuntimeError(
                "accident_model.joblib is not the expected model bundle."
            )
        self.model = bundle["model"]
        self.features = list(bundle.get("features", self.FEATURES))
        self.weather_categories = list(
            bundle.get("weather_categories", [])
        )
        if self.features != self.FEATURES:
            raise RuntimeError(
                "Accident model feature contract mismatch.\n"
                f"Expected: {self.FEATURES}\n"
                f"Model:    {self.features}"
            )
        self.classes = [
            int(x)
            for x in getattr(self.model, "classes_", [])
        ]
        self.loaded = True
    @staticmethod
    def _route_coordinates(route: Any):
        candidate = route
        if isinstance(route, list):
            candidate = route[0] if route else None
        if not isinstance(candidate, dict):
            return []
        geometry = candidate.get("geometry")
        if not isinstance(geometry, dict):
            return []
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list):
            return []
        return [
            point
            for point in coordinates
            if isinstance(point, (list, tuple))
            and len(point) >= 2
        ]
    @classmethod
    def _representative_point(cls, route: Any) -> Tuple[float, float]:
        coordinates = cls._route_coordinates(route)
        if not coordinates:
            raise ValueError(
                "Route geometry is required for accident inference."
            )
        point = coordinates[len(coordinates) // 2]
        lon = float(point[0])
        lat = float(point[1])
        return lat, lon
    @staticmethod
    def _departure_weather(weather: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(weather, dict):
            return {}
        departure = weather.get("departure")
        if isinstance(departure, dict):
            return departure
        return weather
    def _weather_condition_from_code(
        self,
        weather_code: Any,
    ) -> str:
        categories = self.weather_categories
        if not categories:
            return "Unknown"
        try:
            code = int(float(weather_code))
        except (TypeError, ValueError):
            code = None
        groups = {
            "clear": {
                0,
            },
            "cloud": {
                1, 2, 3,
            },
            "fog": {
                45, 48,
            },
            "drizzle": {
                51, 53, 55, 56, 57,
            },
            "rain": {
                61, 63, 65, 66, 67,
                80, 81, 82,
            },
            "snow": {
                71, 73, 75, 77,
                85, 86,
            },
            "storm": {
                95, 96, 99,
            },
        }
        group = next(
            (
                name
                for name, codes in groups.items()
                if code in codes
            ),
            "clear",
        )
        preferred = {
            "clear": (
                "Fair",
                "Clear",
                "Clear Sky",
            ),
            "cloud": (
                "Mostly Cloudy",
                "Partly Cloudy",
                "Scattered Clouds",
                "Overcast",
                "Cloudy",
            ),
            "fog": (
                "Fog",
                "Mist",
            ),
            "drizzle": (
                "Light Drizzle",
                "Drizzle",
            ),
            "rain": (
                "Light Rain",
                "Rain",
                "Heavy Rain",
                "Showers",
            ),
            "snow": (
                "Light Snow",
                "Snow",
                "Heavy Snow",
            ),
            "storm": (
                "Thunderstorms",
                "Thunderstorm",
            ),
        }
        lowered = {
            str(category).strip().lower(): str(category)
            for category in categories
        }
        for candidate in preferred[group]:
            if candidate.lower() in lowered:
                return lowered[candidate.lower()]
        keywords = {
            "clear": ("fair", "clear"),
            "cloud": ("cloud", "overcast"),
            "fog": ("fog", "mist"),
            "drizzle": ("drizzle",),
            "rain": ("rain", "shower"),
            "snow": ("snow",),
            "storm": ("thunder", "storm"),
        }[group]
        for category in categories:
            name = str(category).lower()
            if any(keyword in name for keyword in keywords):
                return str(category)
        if "Unknown" in lowered:
            return lowered["unknown"]
        return str(categories[0])
    @staticmethod
    def _number(value: Any) -> float:
        try:
            number = float(value)
            return number if np.isfinite(number) else np.nan
        except (TypeError, ValueError):
            return np.nan
    def _build_features(
        self,
        route: Any,
        departure_datetime: Optional[datetime],
        weather: Optional[Dict[str, Any]],
    ) -> Tuple[pd.DataFrame, Dict[str, str]]:
        lat, lon = self._representative_point(route)
        w = self._departure_weather(weather)
        temperature_c = self._number(w.get("temperature"))
        humidity = self._number(w.get("relative_humidity"))
        rain_mm = self._number(w.get("rain"))
        weather_code = w.get("weather_code")
        temperature_f = (
            temperature_c * 9.0 / 5.0 + 32.0
            if np.isfinite(temperature_c)
            else np.nan
        )
        precipitation_in = (
            rain_mm / 25.4
            if np.isfinite(rain_mm)
            else np.nan
        )
        condition = self._weather_condition_from_code(
            weather_code
        )
        row = {
            "Start_Lat": lat,
            "Start_Lng": lon,
            "Temperature(F)": temperature_f,
            "Humidity(%)": humidity,
            "Pressure(in)": np.nan,
            "Visibility(mi)": np.nan,
            "Wind_Speed(mph)": np.nan,
            "Precipitation(in)": precipitation_in,
            "Weather_Condition": condition,
            "Junction": 0,
            "Crossing": 0,
            "Traffic_Signal": 0,
            "Stop": 0,
            "Railway": 0,
            "Roundabout": 0,
            "Bump": 0,
            "Traffic_Calming": 0,
        }
        frame = pd.DataFrame(
            [row],
            columns=self.features,
        )
        for col in self.BOOL_FEATURES:
            frame[col] = frame[col].fillna(0).astype("int8")
        frame["Weather_Condition"] = pd.Categorical(
            frame["Weather_Condition"].astype(str),
            categories=self.weather_categories or None,
        )
        sources = {
            "Start_Lat": "route_geometry_midpoint",
            "Start_Lng": "route_geometry_midpoint",
            "Temperature(F)": "Open-Meteo",
            "Humidity(%)": "Open-Meteo",
            "Precipitation(in)": "Open-Meteo_mm_to_inches",
            "Weather_Condition": "Open-Meteo_weather_code_mapping",
            "Pressure(in)": "model_missing_value",
            "Visibility(mi)": "model_missing_value",
            "Wind_Speed(mph)": "model_missing_value",
            "Junction": "default_false",
            "Crossing": "default_false",
            "Traffic_Signal": "default_false",
            "Stop": "default_false",
            "Railway": "default_false",
            "Roundabout": "default_false",
            "Bump": "default_false",
            "Traffic_Calming": "default_false",
        }
        return frame, sources
    def predict(
        self,
        route: Any,
        departure_datetime: Optional[datetime] = None,
        weather: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        frame, sources = self._build_features(
            route=route,
            departure_datetime=departure_datetime,
            weather=weather,
        )
        prediction = self.model.predict(frame)[0]
        probabilities = {}
        confidence = None
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(frame)[0]
            for class_value, probability in zip(
                self.classes,
                proba,
            ):
                probabilities[str(class_value)] = round(
                    float(probability),
                    6,
                )
            if len(proba):
                confidence = float(np.max(proba))
        severity = int(prediction)
        labels = {
            1: "Low",
            2: "Moderate",
            3: "High",
            4: "Severe",
        }
        return {
            "available": True,
            "source": "US_Accident_prediction",
            "model": "LightGBM multiclass Severity",
            "severity": severity,
            "severity_label": labels.get(
                severity,
                f"Severity {severity}",
            ),
            "confidence": round(
                confidence,
                4,
            ) if confidence is not None else None,
            "severity_probabilities": probabilities,
            "risk_level": labels.get(
                severity,
                f"Severity {severity}",
            ),
            "risk": round(
                max(0.0, min(1.0, (severity - 1) / 3.0)),
                4,
            ),
            "severity_risk_index": round(
                max(0.0, min(1.0, (severity - 1) / 3.0)),
                4,
            ),
            "route_data_quality": (
                "partial"
            ),
            "feature_sources": sources,
            "warning": (
                "Severity model uses route midpoint/weather and "
                "defaults unavailable road-context flags to False. "
                "Confidence is class confidence, not accident probability."
            ),
        }
