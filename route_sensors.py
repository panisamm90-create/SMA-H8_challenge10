import numpy as np
import pandas as pd
class RouteSensorMapper:
    def __init__(
        self,
        sensor_locations_path
    ):
        self.sensors = pd.read_csv(
            sensor_locations_path
        )
        self.sensors['sensor_id'] = (
            self.sensors['sensor_id']
            .astype(str)
        )
        self.sensors = (
            self.sensors[
                [
                    'sensor_id',
                    'latitude',
                    'longitude'
                ]
            ]
            .dropna()
            .reset_index(drop=True)
        )
    @staticmethod
    def _distance_km(
        lat1,
        lon1,
        lat2,
        lon2
    ):
        R = 6371.0
        lat1 = np.radians(lat1)
        lat2 = np.radians(lat2)
        dlat = lat2 - lat1
        dlon = (
            np.radians(lon2)
            -
            np.radians(lon1)
        )
        a = (
            np.sin(dlat / 2) ** 2
            +
            np.cos(lat1)
            *
            np.cos(lat2)
            *
            np.sin(dlon / 2) ** 2
        )
        return (
            2
            *
            R
            *
            np.arcsin(
                np.sqrt(a)
            )
        )
    def map_route(
        self,
        route_geometry,
        max_distance_km=1.5
    ):
        coordinates = (
            route_geometry
            ['coordinates']
        )
        if not coordinates:
            return []
        route_points = np.asarray(
            [
                [
                    point[1],
                    point[0]
                ]
                for point in coordinates
            ],
            dtype=np.float32
        )
        max_points = 500
        if len(route_points) > max_points:
            indices = np.linspace(
                0,
                len(route_points) - 1,
                max_points
            ).astype(int)
            route_points = (
                route_points[
                    indices
                ]
            )
        sensor_lat = (
            self.sensors[
                'latitude'
            ]
            .to_numpy(
                dtype=np.float32
            )
        )
        sensor_lon = (
            self.sensors[
                'longitude'
            ]
            .to_numpy(
                dtype=np.float32
            )
        )
        selected = {}
        for lat, lon in route_points:
            distances = self._distance_km(
                lat,
                lon,
                sensor_lat,
                sensor_lon
            )
            nearest_idx = (
                np.argmin(
                    distances
                )
            )
            nearest_distance = (
                float(
                    distances[
                        nearest_idx
                    ]
                )
            )
            if (
                nearest_distance
                <= max_distance_km
            ):
                sensor_id = (
                    self.sensors.iloc[
                        nearest_idx
                    ]['sensor_id']
                )
                selected[
                    sensor_id
                ] = nearest_distance
        result = sorted(
            [
                {
                    'sensor_id': sensor_id,
                    'distance_to_route_km': distance
                }
                for sensor_id, distance
                in selected.items()
            ],
            key=lambda x:
                x[
                    'distance_to_route_km'
                ]
        )
        return result
    def map_routes(
        self,
        routes,
        max_distance_km=1.5
    ):
        results = []
        for route in routes:
            sensors = self.map_route(
                route['geometry'],
                max_distance_km
            )
            route_result = {
                'route_id':
                    route['route_id'],
                'sensor_ids':
                    [
                        item['sensor_id']
                        for item in sensors
                    ],
                'sensor_details':
                    sensors
            }
            results.append(
                route_result
            )
        return results