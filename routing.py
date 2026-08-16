from typing import Any, Dict, List, Tuple
import requests
class RoutingAPI:
    BASE_URL = "https://router.project-osrm.org"
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
    def get_routes(
        self,
        origin: Tuple[float, float],
        dest: Tuple[float, float],
        alternatives: bool = True,
        max_routes: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return up to max_routes OSRM alternatives."""
        max_routes = max(1, min(int(max_routes), 3))
        url = (
            f"{self.BASE_URL}/route/v1/driving/"
            f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        )
        params = {
            "overview": "full",
            "geometries": "geojson",
            "alternatives": "true" if alternatives else "false",
            "steps": "false",
        }
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "Ok":
                print(
                    f"[RouteAPI] OSRM error: "
                    f"{data.get('code')} — "
                    f"{data.get('message', 'unknown error')}"
                )
                return []
            raw_routes = data.get("routes") or []
            routes: List[Dict[str, Any]] = []
            for index, route in enumerate(
                raw_routes[:max_routes],
                start=1,
            ):
                if not isinstance(route, dict):
                    continue
                try:
                    distance = float(route["distance"])
                    duration = float(route["duration"])
                except (KeyError, TypeError, ValueError):
                    continue
                geometry = route.get("geometry")
                if not isinstance(geometry, dict):
                    geometry = {
                        "type": "LineString",
                        "coordinates": [],
                    }
                routes.append(
                    {
                        "route_id": index,
                        "distance": distance,
                        "duration": duration,
                        "geometry": geometry,
                        "distance_km": round(distance / 1000.0, 2),
                        "duration_min": round(duration / 60.0, 1),
                    }
                )
            return routes
        except requests.RequestException as error:
            print(f"[RouteAPI] Request error: {error}")
            return []
        except ValueError as error:
            print(f"[RouteAPI] Invalid JSON response: {error}")
            return []
        except Exception as error:
            print(f"[RouteAPI] Unexpected error: {error}")
            return []
    def get_route(
        self,
        origin: Tuple[float, float],
        dest: Tuple[float, float],
    ):
        """Backward-compatible single-route method."""
        routes = self.get_routes(
            origin=origin,
            dest=dest,
            alternatives=False,
            max_routes=1,
        )
        return routes[0] if routes else None
