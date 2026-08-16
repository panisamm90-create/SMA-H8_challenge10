import tables
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
class METRLATrafficProvider:
    def __init__(
        self,
        dataset_root=None,
    ):
        if dataset_root is None:
            dataset_root = (
                Path(__file__).resolve()
                .parents[2]
                / "dataset"
                / "METR-LA"
            )
        self.dataset_root = Path(
            dataset_root
        )
        self.h5_path = (
            self.dataset_root
            / "METR-LA.h5"
        )
        self.locations_path = (
            self.dataset_root
            / "sensor_locations.csv"
        )
        self.adj_path = (
            self.dataset_root
            / "adj"
            / "adj_MetR-LA.pkl"
        )
        if not self.adj_path.exists():
            fallback = (
                self.dataset_root
                / "adj"
                / "adj_METR-LA.pkl"
            )
            if fallback.exists():
                self.adj_path = fallback
        print("=" * 70)
        print("LOADING METR-LA TRAFFIC PROVIDER")
        print("=" * 70)
        with tables.open_file(self.h5_path, mode="r") as h5:
            node = h5.get_node("/df")
            values = node.block0_values.read()
            columns = node.axis0.read()
            index = node.axis1.read()
        self.speed_df = pd.DataFrame(
            values,
            index=index,
            columns=columns,
        )
        self.speed_df.index = pd.to_datetime(
            self.speed_df.index
        )
        self.speed_df.columns = [
            str(c)
            for c in self.speed_df.columns
        ]
        self.speed_matrix = (
            self.speed_df
            .to_numpy(
                dtype=np.float32
            )
        )
        self.sensor_locations = pd.read_csv(
        self.locations_path
        )
        self.sensor_locations["sensor_id"] = (
            self.sensor_locations["sensor_id"]
            .astype(str)
            .str.strip()
        )
        model_sensor_ids = sorted(
            self.sensor_locations["sensor_id"].unique(),
            key=lambda value: int(value),
        )
        if len(model_sensor_ids) != self.speed_matrix.shape[1]:
            raise RuntimeError(
                "Sensor count mismatch: "
                f"locations={len(model_sensor_ids)}, "
                f"model={self.speed_matrix.shape[1]}"
            )
        self.sensor_ids = model_sensor_ids
        self.sensor_id_mapping = {
            sensor_id: index
            for index, sensor_id in enumerate(
                self.sensor_ids
            )
        }
        adjacency_candidates = (
            self.dataset_root / "adj_MetR-LA.pkl",
            self.dataset_root / "adj_METR-LA.pkl",
            self.dataset_root / "adj" / "adj_MetR-LA.pkl",
            self.dataset_root / "adj" / "adj_METR-LA.pkl",
        )
        self.adj_path = next(
            (
                path
                for path in adjacency_candidates
                if path.exists()
            ),
            None,
        )
        if self.adj_path is None:
            raise FileNotFoundError(
                "METR-LA adjacency file not found. "
                f"Checked: {adjacency_candidates}"
            )
        with open(
            self.adj_path,
            "rb"
        ) as f:
            adj_data = pickle.load(
                f,
                encoding="latin1"
        )
        self.adj_sensor_ids = [
            str(x)
            for x in adj_data[0]
        ]
        adjacency = np.asarray(
            adj_data[2],
            dtype=np.float32
        )
        reordered = np.zeros(
            (
                len(self.sensor_ids),
                len(self.sensor_ids),
            ),
            dtype=np.float32,
        )
        adj_mapping = {
            sensor_id: i
            for i, sensor_id
            in enumerate(
                self.adj_sensor_ids
            )
        }
        for i, sensor_i in enumerate(
            self.sensor_ids
        ):
            old_i = adj_mapping.get(
                sensor_i
            )
            if old_i is None:
                continue
            for j, sensor_j in enumerate(
                self.sensor_ids
            ):
                old_j = adj_mapping.get(
                    sensor_j
                )
                if old_j is None:
                    continue
                reordered[i, j] = (
                    adjacency[
                        old_i,
                        old_j
                    ]
                )
        self.adjacency_matrix = reordered
        row_sum = (
            self.adjacency_matrix
            .sum(axis=1)
        )
        self.adjacency_normalized = (
            self.adjacency_matrix
            /
            np.maximum(
                row_sum[:, None],
                1e-8,
            )
        )
        print(
            "Sensors:",
            len(self.sensor_ids)
        )
        print(
            "Speed matrix:",
            self.speed_matrix.shape
        )
        print(
            "Adjacency:",
            self.adjacency_matrix.shape
        )
        print(
            "Non-zero edges:",
            np.count_nonzero(
                self.adjacency_matrix
            )
        )
        print(
            "Sensor mapping:",
            len(
                self.sensor_id_mapping
            )
        )
        print("=" * 70)
        print("METR-LA PROVIDER READY")
        print("=" * 70)
    def sensor_ids_to_indices(
        self,
        sensor_ids,
    ):
        indices = []
        for sensor_id in sensor_ids:
            sensor_id = str(
                sensor_id
            )
            if sensor_id not in (
                self.sensor_id_mapping
            ):
                continue
            indices.append(
                self.sensor_id_mapping[
                    sensor_id
                ]
            )
        return indices
    def find_matching_time(
        self,
        departure_datetime,
    ):
        departure_datetime = pd.Timestamp(
            departure_datetime
        )
        mask = (
            (self.speed_df.index.dayofweek
             == departure_datetime.dayofweek)
            &
            (self.speed_df.index.hour
             == departure_datetime.hour)
            &
            (self.speed_df.index.minute
             == departure_datetime.minute)
        )
        matches = np.where(
            mask
        )[0]
        if len(matches) == 0:
            mask = (
                (self.speed_df.index.dayofweek
                 == departure_datetime.dayofweek)
                &
                (self.speed_df.index.hour
                 == departure_datetime.hour)
            )
            matches = np.where(
                mask
            )[0]
        if len(matches) == 0:
            raise ValueError(
                "No historical METR-LA "
                "timestep matches the "
                "requested departure."
            )
        return int(
            matches[-1]
        )
    def _build_spatial_features(
        self,
    ):
        speed = (
            self.speed_matrix
        )
        W = (
            self.adjacency_normalized
        )
        neighbor_mean = (
            speed
            @ W.T
        )
        neighbor_lag1 = np.zeros_like(
            neighbor_mean
        )
        neighbor_lag1[1:] = (
            neighbor_mean[:-1]
        )
        neighbor_lag3 = np.zeros_like(
            neighbor_mean
        )
        neighbor_lag3[3:] = (
            neighbor_mean[:-3]
        )
        neighbor_change = (
            neighbor_mean
            -
            neighbor_lag1
        )
        mean_sq = (
            (speed ** 2)
            @ W.T
        )
        variance = np.maximum(
            mean_sq
            -
            neighbor_mean ** 2,
            0.0,
        )
        neighbor_std = np.sqrt(
            variance
        )
        return (
            neighbor_mean.astype(
                np.float32
            ),
            neighbor_lag1.astype(
                np.float32
            ),
            neighbor_lag3.astype(
                np.float32
            ),
            neighbor_change.astype(
                np.float32
            ),
            neighbor_std.astype(
                np.float32
            ),
        )
    def get_inference_context(
        self,
        route_sensor_ids,
        departure_datetime,
        temperature,
        humidity,
        rain=0.0,
        weather_code=0,
    ):
        sensor_indices = (
            self.sensor_ids_to_indices(
                route_sensor_ids
            )
        )
        if len(sensor_indices) == 0:
            raise ValueError(
                "None of the route sensors "
                "exist in METR-LA."
            )
        time_index = (
            self.find_matching_time(
                departure_datetime
            )
        )
        (
            neighbor_mean,
            neighbor_lag1,
            neighbor_lag3,
            neighbor_change,
            neighbor_std,
        ) = self._build_spatial_features()
        index = self.speed_df.index
        hour = (
            index.hour
            .to_numpy(
                dtype=np.float32
            )
        )
        minute = (
            index.minute
            .to_numpy(
                dtype=np.float32
            )
        )
        temperature_arr = np.zeros(
            len(index),
            dtype=np.float32
        )
        humidity_arr = np.zeros(
            len(index),
            dtype=np.float32
        )
        rain_arr = np.zeros(
            len(index),
            dtype=np.float32
        )
        weather_code_arr = np.zeros(
            len(index),
            dtype=np.float32
        )
        temperature_arr[
            time_index
        ] = float(
            temperature
        )
        humidity_arr[
            time_index
        ] = float(
            humidity
        )
        rain_arr[
            time_index
        ] = float(
            rain
        )
        weather_code_arr[
            time_index
        ] = float(
            weather_code
        )
        return {
            "time_index":
                time_index,
            "sensor_indices":
                sensor_indices,
            "speed_matrix":
                self.speed_matrix,
            "neighbor_mean":
                neighbor_mean,
            "neighbor_lag1":
                neighbor_lag1,
            "neighbor_lag3":
                neighbor_lag3,
            "neighbor_change":
                neighbor_change,
            "neighbor_std":
                neighbor_std,
            "temperature":
                temperature_arr,
            "humidity":
                humidity_arr,
            "rain":
                rain_arr,
            "weather_code":
                weather_code_arr,
            "hour":
                hour,
            "minute":
                minute,
            "matched_timestamp":
                str(
                    index[time_index]
                ),
            "sensor_ids":
                [
                    str(x)
                    for x
                    in route_sensor_ids
                    if str(x)
                    in self.sensor_id_mapping
                ],
        }