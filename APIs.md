# External APIs and Services

MATTERS uses a mix of required and optional external services. API keys belong in the project-root `.env` file. Never place real keys in source code or commit them to version control.

## Environment variables

```env
ORS_API_KEY=
TOMTOM_API_KEY=
EVENTS_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
```

## OpenRouteService

- Purpose: primary driving/walking route generation and route alternatives
- Base URL: `https://api.heigit.org/openrouteservice/v2/directions`
- Authentication: `ORS_API_KEY`
- Status in this project: required by the current routing provider

## OSRM

- Purpose: fallback/additional driving alternatives
- Base URL: `https://router.project-osrm.org`
- Authentication: none

## Open-Meteo

- Purpose: hourly temperature, humidity, weather code and rain context
- Endpoint: `https://api.open-meteo.com/v1/forecast`
- Authentication: none

## Nager.Date

- Purpose: United States public-holiday context
- Endpoint pattern: `https://date.nager.at/api/v3/PublicHolidays/{year}/US`
- Authentication: none

## TomTom Traffic

- Purpose: optional real-time traffic-flow enrichment along route samples
- Authentication: `TOMTOM_API_KEY`
- Status: optional; historical traffic ML still works without this key

## PredictHQ

- Purpose: optional route-aware event context and estimated event delay/risk
- Endpoint: `https://api.predicthq.com/v1/events/`
- Authentication: `EVENTS_API_KEY`
- Status: optional

## OpenAI API

- Purpose: optional natural-language explanation of a route recommendation and arrival plan
- Endpoint used by the backend: Responses API
- Authentication: `OPENAI_API_KEY`
- Model: configured with `OPENAI_MODEL`
- Status: optional; scoring remains authoritative and works without OpenAI

## OpenStreetMap and Leaflet

- Purpose: browser map visualization and map tiles
- Leaflet is loaded in `frontend/MATTERS.htm`
- OpenStreetMap tiles do not require a project API key
