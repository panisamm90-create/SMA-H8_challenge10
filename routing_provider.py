import os
import requests
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())
ORS_BASE_URL = (
    "https://api.heigit.org/"
    "openrouteservice/v2/directions"
)
OSRM_URL = "https://router.project-osrm.org"
class RoutingProvider:
    def __init__(self):
        self.ors_api_key = os.getenv("ORS_API_KEY")
    def get_routes(self, origin, destination, max_routes=3, transport_mode="car"):
        if not self.ors_api_key:
            raise RuntimeError("ORS_API_KEY is missing from .env")
        if str(transport_mode).strip().lower() == "walking":
            routes = self._get_ors_alternatives(
                origin,
                destination,
                max_routes,
                profile="foot-walking",
            )
            if not routes:
                routes = self._request_ors(
                    origin,
                    destination,
                    profile="foot-walking",
                )
        else:
            routes = self._get_ors_alternatives(
                origin,
                destination,
                max_routes,
                profile="driving-car",
            )
            if len(routes) < max_routes:
                routes = self._add_distinct_routes(
                    origin,
                    destination,
                    routes,
                    max_routes,
                    profile="driving-car",
                )
            if len(routes) < max_routes:
                routes = self._merge_routes(
                    routes,
                    self._get_osrm_routes(
                        origin,
                        destination,
                        max_routes,
                    ),
                    max_routes,
                )
        for index, route in enumerate(routes[:max_routes], 1):
            route["route_id"] = index
        return routes[:max_routes]
    def _get_ors_alternatives(
        self,
        origin,
        destination,
        max_routes,
        profile="driving-car",
    ):
        return self._request_ors(
            origin,
            destination,
            {
                "alternative_routes": {
                    "target_count": min(max_routes, 3),
                    "share_factor": 0.8,
                    "weight_factor": 2.0,
                }
            },
            profile=profile,
        )
    def _add_distinct_routes(
        self,
        origin,
        destination,
        routes,
        max_routes,
        profile="driving-car",
    ):
        variants = [
            {"options": {"avoid_features": ["highways"]}},
            {"options": {"avoid_features": ["tollways"]}},
            {"options": {"avoid_features": ["ferries"]}},
        ]
        result = list(routes)
        for options in variants:
            if len(result) >= max_routes:
                break
            candidates = self._request_ors(
                origin,
                destination,
                options,
                profile=profile,
            )
            result = self._merge_routes(
                result,
                candidates,
                max_routes,
            )
        return result
    def _request_ors(
        self,
        origin,
        destination,
        extra=None,
        profile="driving-car",
    ):
        body = {
            "coordinates": [
                [origin[1], origin[0]],
                [destination[1], destination[0]],
            ]
        }
        if extra:
            body.update(extra)
        headers = {
            "Authorization": self.ors_api_key,
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
        }
        try:
            url = f"{ORS_BASE_URL}/{profile}/geojson"
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=25,
            )
            if not response.ok:
                print(
                    f"[RoutingProvider] ORS {response.status_code}: "
                    f"{response.text[:300]}"
                )
                return []
            data = response.json()
            routes = []
            for feature in data.get("features", []):
                properties = feature.get("properties", {})
                summary = properties.get("summary", {})
                distance = float(summary.get("distance", 0))
                duration = float(summary.get("duration", 0))
                if distance <= 0 or duration <= 0:
                    continue
                routes.append(
                    {
                        "route_id": len(routes) + 1,
                        "distance": distance,
                        "duration": duration,
                        "geometry": feature.get("geometry", {}),
                        "distance_km": round(distance / 1000, 2),
                        "duration_min": round(duration / 60, 1),
                    }
                )
            return routes
        except requests.RequestException as error:
            print(f"[RoutingProvider] ORS request failed: {error}")
            return []
        except (ValueError, TypeError, KeyError) as error:
            print(f"[RoutingProvider] ORS response invalid: {error}")
            return []
    def _get_osrm_routes(
        self,
        origin,
        destination,
        max_routes,
    ):
        url = (
            f"{OSRM_URL}/route/v1/driving/"
            f"{origin[1]},{origin[0]};"
            f"{destination[1]},{destination[0]}"
        )
        params = {
            "overview": "full",
            "geometries": "geojson",
            "alternatives": "true",
            "steps": "false",
        }
        try:
            response = requests.get(
                url,
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            routes = []
            for route in data.get("routes", [])[:max_routes]:
                distance = float(route["distance"])
                duration = float(route["duration"])
                routes.append(
                    {
                        "route_id": len(routes) + 1,
                        "distance": distance,
                        "duration": duration,
                        "geometry": route.get("geometry", {}),
                        "distance_km": round(distance / 1000, 2),
                        "duration_min": round(duration / 60, 1),
                    }
                )
            return routes
        except (requests.RequestException, ValueError, TypeError, KeyError) as error:
            print(f"[RoutingProvider] OSRM failed: {error}")
            return []
    def _merge_routes(self, current, candidates, max_routes):
        result = list(current)
        signatures = {
            self._signature(route)
            for route in result
        }
        for route in candidates:
            signature = self._signature(route)
            if signature in signatures:
                continue
            signatures.add(signature)
            result.append(route)
            if len(result) >= max_routes:
                break
        return result
    @staticmethod
    def _signature(route):
        geometry = route.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            return (
                round(route.get("distance", 0), -1),
                round(route.get("duration", 0), -1),
            )
        if len(coordinates) > 20:
            sample = (
                coordinates[:10]
                + coordinates[-10:]
            )
        else:
            sample = coordinates
        return tuple(
            (round(point[0], 5), round(point[1], 5))
            for point in sample
        )