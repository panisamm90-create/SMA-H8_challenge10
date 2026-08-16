from datetime import datetime
class EventAccidentContext:
    
    def __init__(self, event_api=None, accident_engine=None):
        self.event_api = event_api
        self.accident_engine = accident_engine
    @staticmethod
    def _normalize_datetime(value):
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value
    def get_events(self, route=None, departure_datetime=None, **kwargs):
        """Delegate event lookup to the real event provider."""
        if route is None:
            route = kwargs.get("route")
        if departure_datetime is None:
            departure_datetime = kwargs.get("departure_datetime")
        if self.event_api is None:
            return {
                "events": [],
                "event_count": 0,
                "has_event": 0,
            }
        departure_datetime = self._normalize_datetime(
            departure_datetime
        )
        try:
            result = self.event_api.get_events(
                route=route,
                departure_datetime=departure_datetime,
            )
        except TypeError:
            result = self.event_api.get_events(
                route,
                departure_datetime,
            )
        if result is None:
            return {
                "events": [],
                "event_count": 0,
                "has_event": 0,
            }
        return result
    def get_context(
        self,
        origin,
        destination,
        departure_datetime,
        route=None,
        weather=None,
        traffic=None,
    ):
        departure_datetime = self._normalize_datetime(
            departure_datetime
        )
        events_context = self.get_events(
            route=route,
            departure_datetime=departure_datetime,
        )
        if not isinstance(events_context, dict):
            events_context = {
                "events": events_context if events_context else [],
                "event_count": len(events_context) if events_context else 0,
                "has_event": int(bool(events_context)),
            }
        accident = None
        if self.accident_engine is not None:
            try:
                accident = self.accident_engine.predict(
                    route=route,
                    departure_datetime=departure_datetime,
                    weather=weather,
                    traffic=traffic,
                    events=events_context,
                )
            except Exception:
                accident = None
        return {
            "events": events_context.get("events", []),
            "event_count": int(
                events_context.get(
                    "event_count",
                    len(events_context.get("events", [])),
                )
            ),
            "has_event": int(
                events_context.get(
                    "has_event",
                    bool(events_context.get("events", [])),
                )
            ),
            "accident": accident,
            "accident_risk": (
                accident.get("risk")
                if isinstance(accident, dict)
                else None
            ),
        }
