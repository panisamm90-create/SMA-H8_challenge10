import os
import sys
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
from api.weather import WeatherAPI
weather_api = WeatherAPI()
weather = weather_api.get_weather(
    latitude=34.0522,
    longitude=-118.2437
)
print(weather)