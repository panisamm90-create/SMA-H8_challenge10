# AI and Route Decision Pipeline

```text
User trip request
      |
      v
Route generation (OpenRouteService / OSRM)
      |
      +-----------------------+
      |                       |
      v                       v
Weather + holidays      Optional live context
(Open-Meteo, Nager)     (TomTom, PredictHQ)
      |                       |
      +-----------+-----------+
                  |
                  v
           Context Engine
                  |
        +---------+---------+
        |                   |
        v                   v
Historical traffic ML   Accident severity ML
(METR-LA, sklearn)      (LightGBM)
        |                   |
        +---------+---------+
                  |
                  v
          Route Scoring Engine
                  |
                  v
      Ranked candidate routes
                  |
          +-------+-------+
          |               |
          v               v
      Leaflet UI     Optional OpenAI
                    explanation/chat
```

## Decision principle

The scoring engine is authoritative. The OpenAI layer does not create routes or override numerical route scores; it only explains already-computed recommendations using the context supplied by the backend.
