# MATTERS - System Architecture

## Overview

MATTERS uses a layered architecture that separates browser UI, API orchestration, context providers, ML inference, and route scoring. The current implementation is optimized for a local academic/demo environment while keeping the modules independent enough for future deployment work.

## Layers

### 1. Frontend

`frontend/MATTERS.htm` provides the interactive Leaflet dashboard. It collects trip inputs, calls the FastAPI endpoints, and renders route candidates, traffic layers, recommendations, saved destinations, and supporting context.

### 2. FastAPI application

`backend/main.py` exposes the public backend endpoints and coordinates the route-analysis workflow.

Main endpoints:

- `GET /health`
- `POST /test`
- `POST /arrival-recommendation`
- `POST /chat`

### 3. Providers

Providers connect the application to routing and external context:

- `routing_provider.py`: OpenRouteService with OSRM fallback/additional alternatives
- `traffic_provider.py`: historical METR-LA sensor data
- `realtime_traffic_provider.py`: optional TomTom traffic
- PredictHQ event provider: route-aware event context
- `weather.py`: Open-Meteo weather
- `holidays.py`: Nager.Date US holidays

### 4. ML and decision engines

- `traffic_engine.py`: Extra Trees + HistGradientBoosting traffic inference
- `accident_engine.py`: LightGBM accident-severity inference
- `route_scoring.py`: combines route and context signals into ranked recommendations
- `trip_services.py`: context orchestration

## Runtime data flow

```text
Browser UI
   |
   v
FastAPI
   |
   v
Generate route candidates
   |
   +--> Weather / Holiday
   +--> Historical traffic ML
   +--> Optional live TomTom traffic
   +--> Optional PredictHQ events
   +--> Accident model
   |
   v
Route scoring
   |
   v
Ranked routes + recommendation
   |
   v
Leaflet dashboard
```

## Design principles

- Separation of concerns
- Graceful degradation for optional services
- Reusable provider/engine modules
- Explicit model and dataset paths
- API-first communication between frontend and backend
- Reproducible Python environment through pinned requirements

## Existing diagrams

The diagrams in `docs/diagrams/` document the earlier architecture design and remain useful as conceptual references. The text in this document reflects the current final implementation.
