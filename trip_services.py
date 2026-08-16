from datetime import datetime
import numpy as np
import pandas as pd
class ContextEngine:
    def __init__(
        self,
        routing_api,
        weather_api,
        holiday_api,
        traffic_engine=None,
        traffic_provider=None,
        event_api=None,
        accident_engine=None,
        realtime_traffic_provider=None,
    ):
        self.routing_api = routing_api
        self.weather_api = weather_api
        self.holiday_api = holiday_api
        self.traffic_engine = traffic_engine
        self.traffic_provider = (
            traffic_provider
            if traffic_provider is not None
            else getattr(traffic_engine, "provider", None)
        )
        self.event_api = event_api
        self.accident_engine = accident_engine
        self.realtime_traffic_provider = realtime_traffic_provider
    def set_traffic_engine(self, traffic_engine):
        self.traffic_engine = traffic_engine
        if self.traffic_provider is None:
            self.traffic_provider = getattr(
                traffic_engine,
                "provider",
                None,
            )
        return self
    def set_traffic_provider(self, traffic_provider):
        self.traffic_provider = traffic_provider
        return self
    def set_event_api(self, event_api):
        self.event_api = event_api
        return self
    def set_accident_engine(self, accident_engine):
        self.accident_engine = accident_engine
        return self
    def set_realtime_traffic_provider(self, provider):
        self.realtime_traffic_provider = provider
        return self
    @staticmethod
    def _build_departure_datetime(
        departure_date,
        departure_time,
    ):
        try:
            return datetime.fromisoformat(
                f"{departure_date}T{departure_time}"
            )
        except ValueError as error:
            raise ValueError(
                "Invalid departure date/time. "
                "Expected YYYY-MM-DD and HH:MM."
            ) from error
    def _get_route(self, origin, destination):
        route = self.routing_api.get_route(
            origin,
            destination,
        )
        if route is None:
            raise RuntimeError(
                "Routing API failed to return a route."
            )
        return route
    def _get_weather(
        self,
        origin,
        departure_datetime,
    ):
        weather = self.weather_api.get_weather(
            latitude=origin[0],
            longitude=origin[1],
            target_datetime=departure_datetime,
        )
        if weather is None:
            raise RuntimeError(
                "Weather API failed."
            )
        return weather
    @staticmethod
    def _extract_departure_weather(weather):
        if isinstance(weather, dict):
            departure = weather.get("departure")
            if isinstance(departure, dict):
                return {
                    "temperature": float(
                        departure.get("temperature", 0.0)
                    ),
                    "humidity": float(
                        departure.get("relative_humidity", 0.0)
                    ),
                    "rain": float(
                        departure.get("rain", 0.0)
                    ),
                    "weather_code": float(
                        departure.get("weather_code", 0.0)
                    ),
                }
        return {
            "temperature": 0.0,
            "humidity": 0.0,
            "rain": 0.0,
            "weather_code": 0.0,
        }
    def _get_holiday(
        self,
        departure_date,
        country="US",
    ):
        holiday = self.holiday_api.is_holiday(
            departure_date,
            country=country,
        )
        if holiday is None:
            raise RuntimeError(
                "Holiday API failed."
            )
        return holiday
    @staticmethod
    def _extract_route_coordinates(route):
        candidate = route
        if isinstance(route, list):
            if not route:
                return []
            candidate = route[0]
        if not isinstance(candidate, dict):
            return []
        geometry = candidate.get("geometry")
        if not isinstance(geometry, dict):
            return []
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list):
            return []
        return coordinates
    def _get_route_sensor_ids(
        self,
        route,
        max_sensors=2,
    ):
        provider = self.traffic_provider
        if provider is None:
            raise RuntimeError("Traffic provider is not connected.")
        locations = getattr(provider, "sensor_locations", None)
        mapping = getattr(provider, "sensor_id_mapping", None)
        sensor_ids = getattr(provider, "sensor_ids", None)
        if locations is None or mapping is None:
            raise RuntimeError("Traffic sensor metadata is unavailable.")
        coordinates = self._extract_route_coordinates(route)
        if not coordinates:
            raise RuntimeError("Route geometry is unavailable.")
        if not {
            "sensor_id",
            "latitude",
            "longitude",
        }.issubset(set(locations.columns)):
            raise RuntimeError(
                "sensor_locations.csv is missing required columns."
            )
        def normalize(value):
            value = str(value).strip()
            if value.endswith(".0"):
                value = value[:-2]
            return value
        locations = locations.copy()
        locations["_location_id"] = (
            locations["sensor_id"].map(normalize)
        )
        normalized_mapping = {
            normalize(key): value
            for key, value in mapping.items()
        }
        known_locations = locations[
            locations["_location_id"].isin(
                normalized_mapping
            )
        ].copy()
        if known_locations.empty:
            if (
                sensor_ids is not None
                and len(sensor_ids) == len(locations)
                and len(sensor_ids) > 0
            ):
                locations["_model_sensor_id"] = [
                    normalize(sensor_id)
                    for sensor_id in sensor_ids
                ]
                known_locations = locations.copy()
                print(
                    "[Traffic] Sensor IDs differ between "
                    "METR-LA files; using dataset row alignment."
                )
            else:
                raise RuntimeError(
                    "sensor_locations.csv and METR-LA.h5 "
                    "contain no matching sensor IDs."
                )
        else:
            known_locations["_model_sensor_id"] = (
                known_locations["_location_id"]
            )
        known_locations["latitude"] = pd.to_numeric(
            known_locations["latitude"],
            errors="coerce",
        )
        known_locations["longitude"] = pd.to_numeric(
            known_locations["longitude"],
            errors="coerce",
        )
        known_locations = known_locations.dropna(
            subset=["latitude", "longitude"]
        )
        route_points = []
        for point in coordinates:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                lon = float(point[0])
                lat = float(point[1])
            except (TypeError, ValueError):
                continue
            if np.isfinite(lon) and np.isfinite(lat):
                route_points.append([lon, lat])
        if not route_points:
            raise RuntimeError("Route geometry contains no valid coordinates.")
        route_xy = np.asarray(route_points, dtype=np.float64)
        if len(route_xy) > 100:
            indices = np.linspace(
                0,
                len(route_xy) - 1,
                100,
                dtype=int,
            )
            route_xy = route_xy[np.unique(indices)]
        sensor_xy = known_locations[
            ["longitude", "latitude"]
        ].to_numpy(dtype=np.float64)
        nearest_distances = np.full(
            len(sensor_xy),
            np.inf,
            dtype=np.float64,
        )
        for point in route_xy:
            distance = np.sum(
                (sensor_xy - point) ** 2,
                axis=1,
            )
            nearest_distances = np.minimum(
                nearest_distances,
                distance,
            )
        nearest_indices = np.argsort(
            nearest_distances
        )[:max_sensors]
        selected = [
            str(
                known_locations.iloc[int(index)][
                    "_model_sensor_id"
                ]
            )
            for index in nearest_indices
        ]
        selected = [
            sensor_id
            for sensor_id in selected
            if sensor_id in normalized_mapping
        ]
        if not selected:
            raise RuntimeError(
                "Nearest route sensors could not be mapped "
                "to METR-LA model indices."
            )
        print(f"[Traffic] Matched sensors: {selected}")
        return selected
    def _get_traffic(
        self,
        route,
        departure_datetime,
        weather,
        holiday=None,
    ):
        if self.traffic_engine is None:
            print(
                "[Traffic] TrafficEngine is not connected."
            )
            return None
        provider = self.traffic_provider
        if provider is None:
            print(
                "[Traffic] TrafficProvider is not connected."
            )
            return None
        try:
            sensor_ids = self._get_route_sensor_ids(
                route,
                max_sensors=2,
            )
            if not sensor_ids:
                raise RuntimeError(
                    "No METR-LA sensors matched this route."
                )
            weather_values = (
                self._extract_departure_weather(
                    weather
                )
            )
            context = provider.get_inference_context(
                route_sensor_ids=sensor_ids,
                departure_datetime=departure_datetime,
                temperature=weather_values["temperature"],
                humidity=weather_values["humidity"],
                rain=weather_values["rain"],
                weather_code=weather_values["weather_code"],
            )
            if not context:
                raise RuntimeError(
                    "Traffic inference context is empty."
                )
            required_features = (
                "speed_matrix",
                "neighbor_mean",
                "neighbor_lag1",
                "neighbor_lag3",
                "neighbor_change",
                "neighbor_std",
                "temperature",
                "humidity",
                "rain",
                "weather_code",
                "hour",
                "minute",
            )
            missing = [
                name
                for name in required_features
                if name not in context
            ]
            if missing:
                raise RuntimeError(
                    f"Traffic context missing: {missing}"
                )
            for name in required_features:
                setattr(
                    self.traffic_engine,
                    name,
                    context[name],
                )
            prediction = self.traffic_engine.predict(
                time_index=context["time_index"],
                sensor_indices=context["sensor_indices"],
            )
            if prediction is None:
                raise RuntimeError(
                    "TrafficEngine returned no prediction."
                )
            prediction["sensor_ids"] = context[
                "sensor_ids"
            ]
            prediction["matched_timestamp"] = (
                context["matched_timestamp"]
            )
            prediction["horizon_minutes"] = context.get(
                "horizon_minutes",
                15,
            )
            live_provider = self.realtime_traffic_provider
            if live_provider is not None and getattr(live_provider, "enabled", False):
                try:
                    minutes_from_now = abs(
                        (departure_datetime - datetime.now()).total_seconds()
                    ) / 60.0
                    live = live_provider.get_route_traffic(route)
                    prediction["realtime"] = live
                    prediction["realtime_available"] = True
                    prediction["traffic_source"] = "tomtom_live"
                    if minutes_from_now <= 20 and live.get("current_speed_kmh") is not None:
                        ml_speeds = [
                            float(x) for x in prediction.get("predicted_speed", [])
                            if x is not None and float(x) > 0
                        ]
                        if ml_speeds:
                            live_speed = float(live["current_speed_kmh"])
                            confidence = float(live.get("confidence") or 0.0)
                            live_weight = min(0.80, max(0.55, confidence * 0.60))
                            ml_mean = sum(ml_speeds) / len(ml_speeds)
                            fused_speed = live_weight * live_speed + (1.0 - live_weight) * ml_mean
                            prediction["predicted_speed"] = [
                                round(fused_speed, 3)
                                for _ in prediction["predicted_speed"]
                            ]
                            prediction["fusion"] = {
                                "mode": "live_ml",
                                "live_weight": round(live_weight, 3),
                                "ml_weight": round(1.0 - live_weight, 3),
                                "departure_offset_minutes": round(minutes_from_now, 2),
                            }
                    else:
                        prediction["fusion"] = {
                            "mode": "ml_forecast_with_live_context",
                            "departure_offset_minutes": round(minutes_from_now, 2),
                        }
                except Exception as live_error:
                    prediction["realtime_available"] = False
                    prediction["traffic_source"] = "metrl_a_ml"
                    prediction["realtime_error"] = str(live_error)
            else:
                prediction["realtime_available"] = False
                prediction["traffic_source"] = "metrl_a_ml"
            return prediction
        except Exception as error:
            print(
                f"[Traffic] Prediction failed: {error}"
            )
            return None
    def _get_events(
        self,
        route,
        departure_datetime,
    ):
        if self.event_api is None:
            return {
                "events": [],
                "event_count": 0,
                "has_event": 0,
            }
        try:
            if hasattr(
                self.event_api,
                "get_events",
            ):
                try:
                    result = self.event_api.get_events(
                        route=route,
                        departure_datetime=departure_datetime,
                    )
                except TypeError:
                    result = self.event_api.get_events(
                        route,
                        departure_datetime,
                    )
            elif hasattr(
                self.event_api,
                "get_context",
            ):
                result = self.event_api.get_context(
                    origin=None,
                    destination=None,
                    departure_datetime=departure_datetime,
                    route=route,
                )
            else:
                raise TypeError(
                    "event_api must provide "
                    "get_events() or get_context()"
                )
            if result is None:
                return {
                    "events": [],
                    "event_count": 0,
                    "has_event": 0,
                }
            if isinstance(result, list):
                return {
                    "events": result,
                    "event_count": len(result),
                    "has_event": int(bool(result)),
                }
            if isinstance(result, dict):
                events = result.get(
                    "events",
                    [],
                )
                result.setdefault(
                    "event_count",
                    len(events),
                )
                result.setdefault(
                    "has_event",
                    int(bool(events)),
                )
                return result
            raise TypeError(
                "Unsupported event provider result."
            )
        except Exception as error:
            print(
                f"[ContextEngine] Event API warning: {error}"
            )
            return {
                "events": [],
                "event_count": 0,
                "has_event": 0,
            }
    def _get_accident_risk(
        self,
        route,
        departure_datetime,
        weather=None,
        traffic=None,
        events=None,
    ):
        if self.accident_engine is None:
            return None
        try:
            return self.accident_engine.predict(
                route=route,
                departure_datetime=departure_datetime,
                weather=weather,
                traffic=traffic,
                events=events,
            )
        except TypeError:
            try:
                return self.accident_engine.predict(
                    route=route,
                    departure_datetime=departure_datetime,
                )
            except Exception as error:
                print(
                    f"[ContextEngine] Accident engine warning: {error}"
                )
                return None
        except Exception as error:
            print(
                f"[ContextEngine] Accident engine warning: {error}"
            )
            return None
    def build_context(
        self,
        origin,
        destination,
        departure_date,
        departure_time,
        transport_mode="car",
        route_preference="fastest",
        country="US",
    ):
        departure_datetime = (
            self._build_departure_datetime(
                departure_date,
                departure_time,
            )
        )
        route = self._get_route(
            origin,
            destination,
        )
        weather = self._get_weather(
            origin,
            departure_datetime,
        )
        holiday = self._get_holiday(
            departure_date,
            country=country,
        )
        events = self._get_events(
            route,
            departure_datetime,
        )
        traffic = self._get_traffic(
            route=route,
            departure_datetime=departure_datetime,
            weather=weather,
            holiday=holiday,
        )
        accident = self._get_accident_risk(
            route=route,
            departure_datetime=departure_datetime,
            weather=weather,
            traffic=traffic,
            events=events,
        )
        return {
            "request": {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "departure_time": departure_time,
                "departure_datetime": (
                    departure_datetime.isoformat()
                ),
                "transport_mode": transport_mode,
                "route_preference": route_preference,
                "country": country,
            },
            "route": route,
            "weather": weather,
            "holiday": holiday,
            "events": events,
            "accident": accident,
            "traffic": traffic,
        }