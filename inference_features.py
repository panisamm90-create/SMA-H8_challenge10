import numpy as np
FEATURES_23 = [
    "speed",
    "lag_1",
    "rolling_mean_3",
    "lag_2",
    "rolling_mean_6",
    "lag_3",
    "lag_4",
    "rolling_mean_12",
    "lag_6",
    "minute",
    "speed_change_3",
    "speed_change_1",
    "hour_cos",
    "temp_humidity_interaction",
    "hour",
    "speed_vs_mean_6",
    "temperature_2m",
    "speed_change_6",
    "relative_humidity_2m",
    "rolling_mean_24",
    "lag_9",
    "hour_sin",
    "lag_12",
]
SPATIAL_FEATURES = [
    "neighbor_mean",
    "neighbor_lag1",
    "neighbor_lag3",
    "neighbor_change",
    "neighbor_std",
]
FINAL_FEATURES = (
    FEATURES_23
    + SPATIAL_FEATURES
)
assert len(FINAL_FEATURES) == 28
def build_inference_features(
    time_index,
    sensor_indices,
    speed_matrix,
    temperature,
    humidity,
    rain,
    weather_code,
    hour,
    minute,
    neighbor_mean,
    neighbor_lag1,
    neighbor_lag3,
    neighbor_change,
    neighbor_std,
):
    """
    Build the exact 28 features expected by the
    final Spatial Extra Trees and HGB models.
    Parameters
    ----------
    time_index : int
        Current traffic timestep.
    sensor_indices : array-like
        Model sensor indices.
    speed_matrix : np.ndarray
        Shape: (time, sensors)
    Weather arrays:
        Shape: (time,)
    Spatial arrays:
        Shape: (time, sensors)
    Returns
    -------
    np.ndarray
        Shape: (n_sensors, 28)
    """
    sensors = np.asarray(
        sensor_indices,
        dtype=np.int32
    )
    t = int(time_index)
    n = len(sensors)
    X = np.empty(
        (n, 28),
        dtype=np.float32
    )
    current = speed_matrix[
        t,
        sensors
    ]
    lag_1 = speed_matrix[
        t - 1,
        sensors
    ]
    lag_2 = speed_matrix[
        t - 2,
        sensors
    ]
    lag_3 = speed_matrix[
        t - 3,
        sensors
    ]
    lag_4 = speed_matrix[
        t - 4,
        sensors
    ]
    lag_6 = speed_matrix[
        t - 6,
        sensors
    ]
    lag_9 = speed_matrix[
        t - 9,
        sensors
    ]
    lag_12 = speed_matrix[
        t - 12,
        sensors
    ]
    rolling_mean_3 = np.mean(
        speed_matrix[
            t - 3:t,
            sensors
        ],
        axis=0
    )
    rolling_mean_6 = np.mean(
        speed_matrix[
            t - 6:t,
            sensors
        ],
        axis=0
    )
    rolling_mean_12 = np.mean(
        speed_matrix[
            t - 12:t,
            sensors
        ],
        axis=0
    )
    rolling_mean_24 = np.mean(
        speed_matrix[
            t - 24:t,
            sensors
        ],
        axis=0
    )
    speed_change_1 = (
        current - lag_1
    )
    speed_change_3 = (
        current - lag_3
    )
    speed_change_6 = (
        current - lag_6
    )
    speed_vs_mean_6 = (
        current /
        (rolling_mean_6 + 1e-6)
    )
    temp = float(
        temperature[t]
    )
    hum = float(
        humidity[t]
    )
    temp_humidity_interaction = (
        temp * hum
    )
    h = float(hour[t])
    m = float(minute[t])
    hour_sin = np.sin(
        2 * np.pi * h / 24
    )
    hour_cos = np.cos(
        2 * np.pi * h / 24
    )
    X[:, 0] = current
    X[:, 1] = lag_1
    X[:, 2] = rolling_mean_3
    X[:, 3] = lag_2
    X[:, 4] = rolling_mean_6
    X[:, 5] = lag_3
    X[:, 6] = lag_4
    X[:, 7] = rolling_mean_12
    X[:, 8] = lag_6
    X[:, 9] = m
    X[:, 10] = speed_change_3
    X[:, 11] = speed_change_1
    X[:, 12] = hour_cos
    X[:, 13] = temp_humidity_interaction
    X[:, 14] = h
    X[:, 15] = speed_vs_mean_6
    X[:, 16] = temp
    X[:, 17] = speed_change_6
    X[:, 18] = hum
    X[:, 19] = rolling_mean_24
    X[:, 20] = lag_9
    X[:, 21] = hour_sin
    X[:, 22] = lag_12
    X[:, 23] = neighbor_mean[
        t,
        sensors
    ]
    X[:, 24] = neighbor_lag1[
        t,
        sensors
    ]
    X[:, 25] = neighbor_lag3[
        t,
        sensors
    ]
    X[:, 26] = neighbor_change[
        t,
        sensors
    ]
    X[:, 27] = neighbor_std[
        t,
        sensors
    ]
    return X