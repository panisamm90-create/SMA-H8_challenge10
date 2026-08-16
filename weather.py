from datetime import datetime
import requests
class WeatherAPI:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    def get_weather(
        self,
        latitude: float,
        longitude: float,
        target_datetime: str | datetime | None = None,
    ):
        if isinstance(target_datetime, str):
            target_datetime = datetime.fromisoformat(target_datetime)
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "weather_code,"
                "rain"
            ),
            "timezone": "auto",
        }
        if target_datetime is not None:
            target_date = target_datetime.date().isoformat()
            params["start_date"] = target_date
            params["end_date"] = target_date
        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            hourly = payload.get("hourly", {})
            result = {
                "time": hourly.get("time", []),
                "temperature": hourly.get("temperature_2m", []),
                "relative_humidity": hourly.get("relative_humidity_2m", []),
                "weather_code": hourly.get("weather_code", []),
                "rain": hourly.get("rain", []),
            }
            n = min(
                len(result["time"]),
                len(result["temperature"]),
                len(result["relative_humidity"]),
                len(result["weather_code"]),
                len(result["rain"]),
            )
            result["time"] = result["time"][:n]
            result["temperature"] = result["temperature"][:n]
            result["relative_humidity"] = result["relative_humidity"][:n]
            result["weather_code"] = result["weather_code"][:n]
            result["rain"] = result["rain"][:n]
            if result["time"]:
                times = [
                    datetime.fromisoformat(t)
                    for t in result["time"]
                ]
                if target_datetime is None:
                    closest_index = 0
                    requested = result["time"][0]
                else:
                    if target_datetime.tzinfo is not None:
                        target_datetime = target_datetime.replace(tzinfo=None)
                    closest_index = min(
                        range(len(times)),
                        key=lambda i: abs(times[i] - target_datetime),
                    )
                    requested = target_datetime.isoformat()
                result["departure"] = {
                    "requested_time": requested,
                    "matched_time": result["time"][closest_index],
                    "temperature": result["temperature"][closest_index],
                    "relative_humidity": result["relative_humidity"][closest_index],
                    "weather_code": result["weather_code"][closest_index],
                    "rain": result["rain"][closest_index],
                }
            return result
        except requests.RequestException as error:
            print(f"[WeatherAPI] Request error: {error}")
            return None
        except (KeyError, ValueError, TypeError) as error:
            print(f"[WeatherAPI] Invalid response: {error}")
            return None
