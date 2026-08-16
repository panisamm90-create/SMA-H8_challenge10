from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import math
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
EVENTS_API_KEY = os.getenv("EVENTS_API_KEY", "").strip()
try:
    from api.weather import WeatherAPI
    from services.routing_final import RoutingAPI
    from api.holidays import HolidayAPI
    from engines.route_scoring import RouteScoringEngine
    from engines.traffic_engine import TrafficEngine
    from providers.traffic_provider import METRLATrafficProvider
    from providers.realtime_traffic_provider import TomTomRealtimeTrafficProvider
    from engines.accident_engine import AccidentEngine
    from services.trip_services import ContextEngine
except ModuleNotFoundError:
    from backend.api.weather import WeatherAPI
    from backend.services.routing_final import RoutingAPI
    from backend.api.holidays import HolidayAPI
    from backend.engines.route_scoring import RouteScoringEngine
    from backend.engines.traffic_engine import TrafficEngine
    from backend.providers.traffic_provider import METRLATrafficProvider
    from backend.providers.realtime_traffic_provider import TomTomRealtimeTrafficProvider
    from backend.engines.accident_engine import AccidentEngine
    from backend.services.trip_services import ContextEngine
app = FastAPI(
    title="MATTERS - Smart Urban Mobility AI",
    version="1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
weather_api = WeatherAPI()
holiday_api = HolidayAPI()
routing_api = RoutingAPI()
scorer = RouteScoringEngine()
traffic_provider = METRLATrafficProvider()
traffic_engine = TrafficEngine()
realtime_traffic_provider = TomTomRealtimeTrafficProvider()
accident_engine = AccidentEngine()
print("[Accident] US Accident Severity model loaded.")
if realtime_traffic_provider.enabled:
    print("[Traffic] TomTom real-time traffic provider enabled.")
else:
    print("[Traffic] TomTom real-time traffic provider disabled: TOMTOM_API_KEY is missing.")
class PredictHQEventProvider:
    """Route-aware PredictHQ Events API provider."""
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
    def _query(self, lat, lon, window_start, window_end):
        params = {
            "within": f"{self.radius_km:g}km@{lat:.6f},{lon:.6f}",
            "active.gte": window_start.isoformat(),
            "active.lte": window_end.isoformat(),
            "limit": "100",
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
                "events": [], "event_count": 0, "has_event": 0,
                "available": False, "source": "predicthq",
                "error": "EVENTS_API_KEY is missing.",
            }
        coords = self._coords(route)
        if not coords:
            return {"events": [], "event_count": 0, "has_event": 0,
                    "available": True, "source": "predicthq"}
        window_start = departure_dt - timedelta(minutes=self.time_window_minutes)
        window_end = departure_dt + timedelta(minutes=self.time_window_minutes)
        seen, errors = {}, []
        for lon, lat in self._sample_points(coords):
            try:
                payload = self._query(lat, lon, window_start, window_end)
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                errors.append(f"HTTP {error.code}: {detail[:180]}")
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
                distance = self._distance_to_route_km(event_lat, event_lon, coords)
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
                if start_dt > window_end or end_dt < window_start:
                    continue
                categories = raw.get("category") or "Event"
                if isinstance(categories, list):
                    categories = ", ".join(str(x) for x in categories)
                venue = raw.get("venue") or {}
                if not isinstance(venue, dict):
                    venue = {}
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
                    "predicted_attendance": raw.get("phq_attendance") or raw.get("predicted_attendance"),
                    "url": raw.get("webpage"),
                }
        events = sorted(seen.values(), key=lambda e: e["distance_to_route_km"])[:100]
        return {
            "events": events,
            "event_count": len(events),
            "has_event": int(bool(events)),
            "available": True,
            "source": "predicthq",
            **self._impact(events),
            "warning": "Event delay is an estimate, not live measured event traffic." if events else None,
            "error": "; ".join(errors[:2]) if errors and not events else None,
        }
event_api = PredictHQEventProvider(EVENTS_API_KEY, radius_km=8.0, time_window_minutes=240)
print("[Events] PredictHQ Events API enabled." if event_api.enabled
      else "[Events] PredictHQ disabled: EVENTS_API_KEY is missing.")
traffic_context_engine = ContextEngine(
    routing_api=routing_api,
    weather_api=weather_api,
    holiday_api=holiday_api,
    traffic_engine=traffic_engine,
    traffic_provider=traffic_provider,
    event_api=event_api,
    realtime_traffic_provider=realtime_traffic_provider,
)
if traffic_context_engine.traffic_provider is None:
    raise RuntimeError(
        "Traffic provider failed to connect to ContextEngine."
    )
print("[Traffic] Traffic provider connected.")
print("[Traffic] Traffic ML engine connected.")
print("[Traffic] Context engine connected.")
class RouteRequest(BaseModel):
    start_lat: float
    start_lng: float
    dest_lat: float
    dest_lng: float
    departure_date: str = "2026-08-10"
    departure_time: str = "08:30"
    transport_mode: str = "car"
    route_preference: str = "fastest"
class ArrivalRequest(BaseModel):
    start_lat: float
    start_lng: float
    dest_lat: float
    dest_lng: float
    arrival_date: str
    arrival_time: str
    transport_mode: str = "car"
    route_preference: str = "fastest"
    search_window_minutes: int = 180
def _get_routes(request: RouteRequest) -> List[Dict[str, Any]]:
    origin = (request.start_lat, request.start_lng)
    destination = (request.dest_lat, request.dest_lng)
    routes = routing_api.get_routes(
        origin=origin,
        dest=destination,
        alternatives=True,
        max_routes=3,
        transport_mode=request.transport_mode,
    )
    if not routes:
        raise RuntimeError(
            "No route was returned by the route provider."
        )
    print(f"[Routing] {len(routes)} route(s) generated.")
    return routes
@app.get("/")
def root():
    return {
        "success": True,
        "message": "Backend is running successfully.",
        "service": "MATTERS",
    }
@app.get("/events-debug")
def events_debug():
    """Debug PredictHQ connectivity without exposing the API key."""
    return {
        "success": True,
        "predicthq_enabled": bool(EVENTS_API_KEY),
        "provider_enabled": bool(event_api and event_api.enabled),
        "radius_km": event_api.radius_km if event_api else None,
        "time_window_minutes": event_api.time_window_minutes if event_api else None,
        "message": (
            "PredictHQ API key is loaded."
            if EVENTS_API_KEY
            else "EVENTS_API_KEY is missing from the backend environment."
        ),
    }
@app.get("/health")
def health():
    return {
        "success": True,
        "service": "MATTERS",
        "status": "ok",
        "traffic": {
            "ml": traffic_context_engine.traffic_engine is not None,
            "realtime": realtime_traffic_provider.enabled,
            "realtime_source": "tomtom" if realtime_traffic_provider.enabled else None,
            "accident_model": accident_engine.loaded,
        },
        "events": {
            "enabled": event_api is not None and event_api.enabled,
            "source": "predicthq" if event_api is not None and event_api.enabled else None,
        },
    }
def _predict_traffic_for_route(
    route,
    departure_dt,
    weather,
):
    return traffic_context_engine._get_traffic(
        route=route,
        departure_datetime=departure_dt,
        weather=weather,
        holiday=None,
    )
def _get_events_for_route(
    route,
    departure_dt,
):
    if event_api is None or not event_api.enabled:
        return {
            "events": [],
            "event_count": 0,
            "has_event": 0,
            "available": False,
            "source": "predicthq",
            "error": "EVENTS_API_KEY is missing.",
        }
    return event_api.get_events(
        route=route,
        departure_dt=departure_dt,
    )
class ChatRequest(BaseModel):
    message: str
    route_context: Dict[str, Any] = Field(default_factory=dict)
def _extract_openai_text(payload: Dict[str, Any]) -> str:
    """Extract text from the OpenAI Responses API response."""
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            value = content.get("text")
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    return "\n".join(parts).strip()
def _call_openai_route_recommendation(request: ChatRequest) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. Add it to .env in the project root."
        )
    context = request.route_context or {}
    system_prompt = (
        "You are the AI recommendation assistant inside an urban mobility route "
        "planner. Explain the already-computed recommendation; do NOT invent "
        "routes, traffic values, weather, fuel, CO2, or other facts. The scoring "
        "engine is authoritative. Be concise (2-4 sentences), friendly, and clear. "
        "Mention the selected preference, predicted travel time, distance, traffic, "
        "and fuel/CO2 when available. If a value is unavailable, omit it. "
        "If the request is an arrival-time plan, clearly state the recommended departure "
        "time, target arrival time, selected route, expected travel time, and a short "
        "reason. Do not claim a route or time that is not present in the supplied context."
    )
    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "request": request.message,
                        "route_context": context,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "max_output_tokens": 220,
    }
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(http_request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            detail_json = json.loads(detail)
            message = detail_json.get("error", {}).get("message") or detail
        except Exception:
            message = detail
        raise RuntimeError(
            f"OpenAI API error ({error.code}): {message}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not reach OpenAI API: {error.reason}"
        ) from error
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("OpenAI returned invalid JSON.") from error
    reply = _extract_openai_text(result)
    if not reply:
        raise RuntimeError("OpenAI returned an empty recommendation.")
    return reply
@app.post("/chat")
def chat_route(request: ChatRequest):
    try:
        reply = _call_openai_route_recommendation(request)
        return {
            "success": True,
            "reply": reply,
            "model": OPENAI_MODEL,
        }
    except Exception as error:
        print(f"[OpenAI] Recommendation failed: {error}")
        return {
            "success": False,
            "error": str(error),
        }
@app.post("/arrival-recommendation")
def arrival_recommendation(request: ArrivalRequest):
    """Find the latest practical departure time that reaches the requested arrival time."""
    try:
        target = datetime.fromisoformat(
            f"{request.arrival_date}T{request.arrival_time}"
        )
    except ValueError as error:
        return {
            "success": False,
            "stage": "arrival_time",
            "error": "Invalid arrival date/time. Expected YYYY-MM-DD and HH:MM.",
        }
    window = max(30, min(int(request.search_window_minutes), 360))
    origin = (request.start_lat, request.start_lng)
    destination = (request.dest_lat, request.dest_lng)
    candidates = []
    try:
        routes = routing_api.get_routes(
            origin=origin,
            dest=destination,
            alternatives=True,
            max_routes=3,
            transport_mode=request.transport_mode,
        )
    except Exception as error:
        return {
            "success": False,
            "stage": "routing",
            "error": f"Could not generate routes: {error}",
        }
    if not routes:
        return {
            "success": False,
            "stage": "routing",
            "error": "No route was returned by the route provider.",
        }
    for minutes_before in range(0, window + 1, 15):
        departure_dt = target - timedelta(minutes=minutes_before)
        try:
            weather = None
            try:
                weather = weather_api.get_weather(
                    latitude=request.start_lat,
                    longitude=request.start_lng,
                    target_datetime=departure_dt,
                )
            except Exception as error:
                print(f"[Arrival Weather] unavailable: {error}")
            traffic = []
            events = []
            for route in routes:
                try:
                    prediction = _predict_traffic_for_route(
                        route, departure_dt, weather
                    )
                except Exception as error:
                    print(
                        f"[Arrival Traffic] Route {route.get('route_id')} unavailable: {error}"
                    )
                    prediction = {
                        "route_id": route.get("route_id"),
                        "predicted_speed": [],
                        "available": False,
                        "error": str(error),
                    }
                traffic.append(prediction)
                try:
                    event_data = _get_events_for_route(route, departure_dt)
                except Exception as error:
                    print(
                        f"[Arrival Events] Route {route.get('route_id')} unavailable: {error}"
                    )
                    event_data = {
                        "events": [],
                        "event_count": 0,
                        "has_event": 0,
                        "available": False,
                        "error": str(error),
                    }
                events.append(event_data)
            scoring = scorer.rank_routes(
                routes=routes,
                traffic=traffic,
                weather=weather,
                events=events,
                accident=None,
                preference=request.route_preference,
            )
            best = scoring.get("best_route")
            if not best:
                continue
            duration = float(
                best.get("predicted_duration_min")
                or best.get("baseline_duration_min")
                or 0
            )
            expected_arrival = departure_dt + timedelta(minutes=duration)
            candidates.append({
                "departure_time": departure_dt.strftime("%H:%M"),
                "departure_datetime": departure_dt.isoformat(),
                "expected_arrival_time": expected_arrival.strftime("%H:%M"),
                "expected_arrival_datetime": expected_arrival.isoformat(),
                "arrival_on_time": expected_arrival <= target,
                "target_arrival_time": target.strftime("%H:%M"),
                "route_id": best.get("route_id"),
                "duration_min": round(duration, 1),
                "distance_km": best.get("distance_km"),
                "traffic_level": best.get("traffic_level", "Unavailable"),
                "predicted_speed_kmh": best.get("predicted_speed_kmh"),
                "score_100": best.get("score_100"),
                "preference": best.get("preference", request.route_preference),
                "explanation": best.get("explanation", []),
                "estimated_fuel_l": best.get("estimated_fuel_l"),
                "estimated_co2_kg": best.get("estimated_co2_kg"),
            })
        except Exception as error:
            print(f"[Arrival] candidate {minutes_before}m failed: {error}")
    if not candidates:
        return {
            "success": False,
            "stage": "arrival_recommendation",
            "error": "Could not calculate any route candidates for the requested arrival time.",
        }
    on_time = [item for item in candidates if item["arrival_on_time"]]
    if on_time:
        plan = on_time[0]
        plan["status"] = "on_time"
    else:
        plan = min(candidates, key=lambda item: item["expected_arrival_datetime"])
        plan["status"] = "late_risk"
    route_context = {
        "arrival_plan": plan,
        "target_arrival_datetime": target.isoformat(),
        "candidate_count": len(candidates),
        "search_window_minutes": window,
        "transport_mode": request.transport_mode,
        "route_preference": request.route_preference,
    }
    try:
        ai_reply = _call_openai_route_recommendation(
            ChatRequest(
                message=(
                    "Create the final arrival-time driving recommendation. "
                    "Tell the user when to leave, which route to take, whether the "
                    "target arrival is achievable, and the key reason."
                ),
                route_context=route_context,
            )
        )
    except Exception as error:
        print(f"[OpenAI] Arrival recommendation failed: {error}")
        if plan["status"] == "on_time":
            ai_reply = (
                f"Leave at {plan['departure_time']} and take Route {plan['route_id']}. "
                f"Estimated travel time is {plan['duration_min']:.0f} minutes, "
                f"with an expected arrival around {plan['expected_arrival_time']}."
            )
        else:
            ai_reply = (
                f"The requested arrival time could not be guaranteed. "
                f"The best available plan is to leave at {plan['departure_time']} "
                f"via Route {plan['route_id']}, arriving around {plan['expected_arrival_time']}."
            )
    return {
        "success": True,
        "plan": plan,
        "candidates": candidates,
        "reply": ai_reply,
        "model": OPENAI_MODEL,
    }
@app.post("/test")
def test_route(request: RouteRequest):
    try:
        routes = _get_routes(request)
    except Exception as error:
        return {
            "success": False,
            "stage": "routing",
            "error": str(error),
        }
    if not routes:
        return {
            "success": False,
            "stage": "routing",
            "error": "No route was returned by the route provider.",
        }
    try:
        departure_dt = datetime.fromisoformat(
            f"{request.departure_date}T{request.departure_time}"
        )
    except Exception:
        departure_dt = datetime.now()
    weather = None
    try:
        weather = weather_api.get_weather(
            latitude=request.start_lat,
            longitude=request.start_lng,
            target_datetime=departure_dt,
        )
    except Exception as error:
        print(f"[Weather] unavailable: {error}")
        try:
            weather = weather_api.get_weather(
                latitude=request.start_lat,
                longitude=request.start_lng,
            )
        except Exception as fallback_error:
            print(f"[Weather fallback] unavailable: {fallback_error}")
            weather = None
    holiday = None
    try:
        holiday = holiday_api.is_holiday(
            date=request.departure_date,
            country="US",
        )
    except Exception as error:
        print(f"[Holiday] unavailable: {error}")
    if request.transport_mode == "walking":
        traffic_by_route = [
            {
                "route_id": route.get("route_id"),
                "predicted_speed": [],
                "available": False,
                "source": "not_applicable",
            }
            for route in routes
        ]
    else:
        traffic_by_route = []
        for route in routes:
            try:
                prediction = _predict_traffic_for_route(
                    route,
                    departure_dt,
                    weather,
                )
            except Exception as error:
                print(
                    f"[Traffic] Route {route.get('route_id')} unavailable: {error}"
                )
                prediction = {
                    "route_id": route.get("route_id"),
                    "predicted_speed": [],
                    "available": False,
                    "error": str(error),
                }
            if isinstance(prediction, dict):
                prediction["route_id"] = route.get("route_id")
                realtime = prediction.get("realtime")
                if isinstance(realtime, dict):
                    prediction["live"] = bool(realtime.get("live"))
                    prediction["source"] = realtime.get("source", "tomtom")
            traffic_by_route.append(prediction)
    traffic_available = all(
        isinstance(item, dict)
        and isinstance(item.get("predicted_speed"), list)
        for item in traffic_by_route
    )
    print(
        "[Traffic] Predictions generated for "
        f"{sum(isinstance(item, dict) for item in traffic_by_route)}/"
        f"{len(routes)} routes."
    )
    events_by_route = []
    for route in routes:
        try:
            events = _get_events_for_route(
                route,
                departure_dt,
            )
        except Exception as error:
            print(
                f"[Events] Route {route.get('route_id')} unavailable: {error}"
            )
            events = {
                "events": [],
                "event_count": 0,
                "has_event": 0,
                "available": False,
                "error": str(error),
            }
        events_by_route.append(events)
    events_available = event_api is not None
    print(
        "[Events] Matched events for "
        f"{sum(item.get('event_count', 0) > 0 for item in events_by_route)}"
        f"/{len(routes)} routes."
    )
    for index, route in enumerate(routes):
        event_ctx = events_by_route[index] if index < len(events_by_route) else {}
        delay = float(event_ctx.get("estimated_delay_min") or 0.0)
        if delay <= 0 or request.transport_mode == "walking":
            continue
        traffic_ctx = traffic_by_route[index] if index < len(traffic_by_route) else {}
        if not isinstance(traffic_ctx, dict):
            continue
        distance_km = float(route.get("distance_km") or 0.0)
        speeds = traffic_ctx.get("predicted_speed") or []
        valid = [float(s) for s in speeds if isinstance(s, (int, float)) and float(s) > 0]
        if distance_km <= 0 or not valid:
            continue
        base_speed = sum(valid) / len(valid)
        base_duration = distance_km / base_speed * 60.0
        effective_duration = base_duration + delay
        effective_speed = distance_km / effective_duration * 60.0 if effective_duration > 0 else base_speed
        traffic_ctx["predicted_speed"] = [round(effective_speed, 2) for _ in speeds]
        traffic_ctx["event_delay_min"] = round(delay, 1)
        traffic_ctx["event_delay_risk"] = event_ctx.get("delay_risk")
        traffic_ctx["event_delay_risk_percent"] = event_ctx.get("delay_risk_percent")
    accident_by_route = []
    for route in routes:
        try:
            accident = accident_engine.predict(
                route=route,
                departure_datetime=departure_dt,
                weather=weather,
            )
            if isinstance(accident, dict):
                accident["route_id"] = route.get("route_id")
            accident_by_route.append(accident)
        except Exception as error:
            print(
                f"[Accident] Route "
                f"{route.get('route_id')} failed: {error}"
            )
            accident_by_route.append({
                "available": False,
                "error": str(error),
                "route_id": route.get("route_id"),
            })
    accident_available = any(
        isinstance(item, dict)
        and item.get("available") is True
        for item in accident_by_route
    )
    print(
        "[Accident] Severity predictions generated for "
        f"{sum(isinstance(item, dict) and item.get('available') is True for item in accident_by_route)}"
        f"/{len(routes)} routes."
    )
    try:
        scoring = scorer.rank_routes(
            routes=routes,
            traffic=traffic_by_route,
            weather=weather,
            events=events_by_route,
            accident=accident_by_route,
            preference=request.route_preference,
        )
    except Exception as error:
        return {
            "success": False,
            "stage": "scoring",
            "error": f"Route scoring failed: {error}",
            "routes": routes,
            "weather": weather,
            "holiday": holiday,
            "events": events_by_route,
        }
    fuel_summary = [
        {
            "route_id": item.get("route_id"),
            "estimated_fuel_l": item.get("estimated_fuel_l"),
            "estimated_co2_kg": item.get("estimated_co2_kg"),
            "fuel_consumption_l_per_100km": item.get("fuel", {}).get("fuel_consumption_l_per_100km"),
            "estimation_basis": item.get("fuel", {}).get("estimation_basis"),
        }
        for item in scoring.get("ranked_routes", [])
    ]
    map_routes = []
    for route in routes:
        geometry = route.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        map_routes.append({
            "route_id": route.get("route_id"),
            "coordinates": coordinates,
            "distance_km": route.get("distance_km"),
            "duration_min": route.get("duration_min"),
        })
    map_events = []
    for route_events in events_by_route:
        if not isinstance(route_events, dict):
            continue
        for event in route_events.get("events") or []:
            if not isinstance(event, dict):
                continue
            if event.get("latitude") is None or event.get("longitude") is None:
                continue
            map_events.append({
                "route_id": event.get("route_id"),
                "event_name": event.get("event_name", "Event"),
                "latitude": event.get("latitude"),
                "longitude": event.get("longitude"),
                "distance_to_route_km": event.get("distance_to_route_km"),
                "venue": event.get("venue"),
                "start": event.get("start"),
                "event_type": event.get("event_type"),
                "url": event.get("url"),
            })
    return {
        "success": True,
        "routes": routes,
        "scoring": scoring,
        "map_data": {
            "origin": {"lat": request.start_lat, "lng": request.start_lng},
            "destination": {"lat": request.dest_lat, "lng": request.dest_lng},
            "routes": map_routes,
            "events": map_events[:100],
        },
        "fuel_co2": fuel_summary,
        "best_route_id": scoring.get("best_route_id"),
        "weather": weather,
        "holiday": holiday,
        "traffic": traffic_by_route,
        "traffic_available": traffic_available,
        "realtime_traffic": {
            "enabled": realtime_traffic_provider.enabled,
            "source": "tomtom" if realtime_traffic_provider.enabled else None,
            "fused": any(
                isinstance(item, dict) and item.get("fusion", {}).get("mode") == "live_ml"
                for item in traffic_by_route
            ),
        },
        "events": events_by_route,
        "events_available": events_available,
        "event_source": "ticketmaster" if event_api.enabled else None,
        "accident": accident_by_route,
        "accident_available": accident_available,
        "transport_mode": request.transport_mode,
        "route_preference": scoring.get("preference", request.route_preference),
        "selection": {
            "preference": scoring.get("preference", request.route_preference),
            "best_route_id": scoring.get("best_route_id"),
            "traffic_optimized": scoring.get("preference") == "least_traffic",
            "eco_optimized": scoring.get("preference") == "eco",
        },
    }
