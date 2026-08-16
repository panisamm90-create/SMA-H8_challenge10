import math
import json
from datetime import timedelta
import urllib
import requests

class PredictHQEventProvider:
    API_URL = "https://api.predicthq.com/v1/events/"
    def __init__(self, api_key: str, radius_km: float = 8.0,
                 time_window_minutes: int = 240):
        self.api_key = api_key
        self.radius_km = float(radius_km)
        self.time_window_minutes = int(time_window_minutes)
        self.enabled = bool(api_key)
    @staticmethod
    def _coords(route):
        coords = (route.get("geometry") or {}).get("coordinates") or []
        out = []
        for c in coords:
            try:
                if len(c) >= 2:
                    out.append([float(c[0]), float(c[1])])
            except (TypeError, ValueError):
                pass
        return out
    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        r = 6371.0088
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(min(1.0, a)))
    @classmethod
    def _distance_to_route_km(cls, lat, lon, coords):
        if not coords:
            return float("inf")
        return min(
            cls._haversine_km(lat, lon, route_lat, route_lon)
            for route_lon, route_lat in coords
        )
    @staticmethod
    def _sample_points(coords, maximum=8):
        if len(coords) <= maximum:
            return coords
        step = (len(coords) - 1) / float(maximum - 1)
        return [coords[round(i * step)] for i in range(maximum)]
    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except (TypeError, ValueError):
            return None
    @staticmethod
    def _event_lat_lon(event):
        location = event.get("location")
        if isinstance(location, list) and len(location) >= 2:
            try:
                return float(location[1]), float(location[0])
            except (TypeError, ValueError):
                return None
        return None
    @staticmethod
    def _type_multiplier(event):
        category = event.get("category") or ""
        blob = f"{event.get('title') or ''} {category}".lower()
        if any(x in blob for x in ("sports", "sport", "football", "soccer", "basketball", "baseball", "hockey")):
            return 1.5
        if any(x in blob for x in ("concert", "music", "festival")):
            return 1.4
        if any(x in blob for x in ("theater", "theatre", "comedy", "performing-arts")):
            return 0.9
        if any(x in blob for x in ("conference", "exhibition", "expo")):
            return 1.1
        return 1.0
    def _impact(self, events):
        if not events:
            return {"estimated_delay_min": 0.0, "delay_risk_percent": 0,
                    "delay_risk": "Low", "event_score": 0.0}
        total = 0.0
        for event in events:
            distance = float(event.get("distance_to_route_km") or self.radius_km)
            proximity = max(0.05, 1.0 - min(distance / self.radius_km, 1.0))
            try:
                attendance = float(event.get("predicted_attendance") or 0)
            except (TypeError, ValueError):
                attendance = 0.0
            attendance_factor = min(2.0, 1.0 + math.log10(max(attendance, 1.0)) / 5.0)
            total += (2.0 + 5.0 * proximity) * self._type_multiplier(event) * attendance_factor
        total = min(25.0, total * (0.72 + 0.28 / max(1, len(events))))
        risk = int(round(min(95.0, 15.0 + total * 3.8)))
        return {
            "estimated_delay_min": round(total, 1),
            "delay_risk_percent": risk,
            "delay_risk": "High" if risk >= 65 else "Moderate" if risk >= 40 else "Low",
            "event_score": round(min(1.0, total / 18.0), 3),
        }
    def _query(self, lat, lon, search_start, search_end):
        """
        Query PredictHQ for events around one route sample point.
        PredictHQ's official Events API supports:
          - within = radius@lat,lon
          - active.gte / active.lte
          - state=active,predicted
          - category filtering
        """
        params = {
            "within": f"{self.radius_km:g}km@{lat:.6f},{lon:.6f}",
            "active.gte": search_start.strftime("%Y-%m-%dT%H:%M:%S"),
            "active.lte": search_end.strftime("%Y-%m-%dT%H:%M:%S"),
            "active.tz": "Europe/Berlin",
            "state": "active,predicted",
            "limit": "100",
            "sort": "rank",
        }
        request = urllib.request.Request(
            f"{self.API_URL}?{urllib.parse.urlencode(params)}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    def get_events(self, route, departure_dt):
        if not self.enabled:
            return {
                "events": [],
                "event_count": 0,
                "has_event": 0,
                "available": False,
                "source": "predicthq",
                "error": "EVENTS_API_KEY is missing.",
            }
        coords = self._coords(route)
        if not coords:
            return {
                "events": [],
                "event_count": 0,
                "has_event": 0,
                "available": True,
                "source": "predicthq",
            }
        search_start = departure_dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        search_end = search_start + timedelta(days=1)
        trip_start = departure_dt - timedelta(minutes=self.time_window_minutes)
        trip_end = departure_dt + timedelta(minutes=self.time_window_minutes)
        seen = {}
        errors = []
        for lon, lat in self._sample_points(coords):
            try:
                payload = self._query(
                    lat,
                    lon,
                    search_start,
                    search_end,
                )
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                errors.append(f"HTTP {error.code}: {detail[:250]}")
                continue
            except Exception as error:
                errors.append(str(error))
                continue
            for raw in payload.get("results", []) or []:
                event_id = str(raw.get("id") or "")
                if not event_id or event_id in seen:
                    continue
                geo = raw.get("geo") or {}
                geometry = geo.get("geometry") or {}
                coordinates = geometry.get("coordinates") or []
                event_lat = event_lon = None
                if (
                    isinstance(coordinates, list)
                    and len(coordinates) >= 2
                    and isinstance(coordinates[0], (int, float))
                    and isinstance(coordinates[1], (int, float))
                ):
                    event_lon = float(coordinates[0])
                    event_lat = float(coordinates[1])
                if event_lat is None:
                    lat_lon = self._event_lat_lon(raw)
                    if lat_lon:
                        event_lat, event_lon = lat_lon
                if event_lat is None:
                    continue
                distance = self._distance_to_route_km(
                    event_lat,
                    event_lon,
                    coords,
                )
                if distance > self.radius_km:
                    continue
                start_dt = self._parse_datetime(raw.get("start"))
                end_dt = self._parse_datetime(raw.get("end"))
                if start_dt is None:
                    active = raw.get("active") or {}
                    start_dt = self._parse_datetime(active.get("start"))
                    end_dt = self._parse_datetime(active.get("end"))
                if start_dt is None:
                    continue
                if end_dt is None:
                    end_dt = start_dt + timedelta(hours=3)
                if start_dt > trip_end or end_dt < trip_start:
                    continue
                categories = raw.get("category") or "Event"
                if isinstance(categories, list):
                    categories = ", ".join(str(x) for x in categories)
                venue = raw.get("venue") or {}
                if not isinstance(venue, dict):
                    venue = {}
                attendance = raw.get("phq_attendance")
                if attendance is None:
                    attendance = raw.get("predicted_attendance")
                seen[event_id] = {
                    "event_id": event_id,
                    "route_id": route.get("route_id"),
                    "event_name": raw.get("title") or "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "latitude": event_lat,
                    "longitude": event_lon,
                    "venue": venue.get("name"),
                    "distance_to_route_km": round(distance, 3),
                    "time_overlap": True,
                    "event_type": str(categories),
                    "predicted_attendance": attendance,
                    "phq_rank": raw.get("rank"),
                    "url": raw.get("webpage"),
                }
        events = sorted(
            seen.values(),
            key=lambda e: e["distance_to_route_km"],
        )[:100]
        return {
            "events": events,
            "event_count": len(events),
            "has_event": int(bool(events)),
            "available": True,
            "source": "predicthq",
            **self._impact(events),
            "warning": (
                "Event delay is an estimate, not live measured event traffic."
                if events else None
            ),
            "error": "; ".join(errors[:2]) if errors and not events else None,
        }
