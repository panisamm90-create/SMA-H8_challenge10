"""Quick smoke test for the accident engine.
Run from project root after training:
    python backend/engines/test_accident_engine.py
"""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from accident_engine import AccidentEngine
ROUTE = {
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [-73.9857, 40.7580],
            [-73.9820, 40.7560],
            [-73.9780, 40.7520],
            [-73.9740, 40.7484],
        ]
    }
}
WEATHER = {
    "departure": {
        "temperature": 24.0,
        "relative_humidity": 55.0,
        "rain": 0.0,
        "weather_code": 0,
    }
}
engine = AccidentEngine()
if not engine.loaded:
    print("ACCIDENT MODEL NOT READY")
    print(engine.load_error)
    raise SystemExit(1)
result = engine.predict(
    route=ROUTE,
    departure_datetime="2026-08-12T09:00:00",
    weather=WEATHER,
)
print("=" * 70)
print("ACCIDENT ENGINE TEST")
print("=" * 70)
print("Available       :", result["available"])
print("Risk level      :", result["risk_level"])
print("Risk score      :", result["risk_score"])
print("Predicted       :", result["severity_label"])
print("Severity probs  :", result["severity_probabilities"])
print("Points evaluated:", result["route_points_evaluated"])
print("=" * 70)
