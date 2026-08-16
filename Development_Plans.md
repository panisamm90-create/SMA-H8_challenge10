# MATTERS - Current Status and Roadmap

## Completed in the current prototype

- [x] METR-LA historical traffic data integration
- [x] Traffic feature engineering and inference
- [x] Extra Trees + HistGradientBoosting traffic models
- [x] Multi-route generation and comparison
- [x] Route scoring engine
- [x] ETA and route recommendation
- [x] Weather integration
- [x] Holiday integration
- [x] Optional TomTom live traffic integration
- [x] Optional PredictHQ event integration
- [x] Accident-severity ML model
- [x] Arrival-time recommendation
- [x] Leaflet dashboard
- [x] Frontend-to-backend integration
- [x] Optional AI recommendation explanation

## Recommended next improvements

- [ ] Add automated end-to-end API tests
- [ ] Add structured logging instead of print statements
- [ ] Add caching/rate-limit management for external APIs
- [ ] Calibrate route-scoring weights with evaluation data
- [ ] Quantify confidence and sensor coverage per route
- [ ] Add deployment configuration (Docker/reverse proxy)
- [ ] Restrict CORS for production deployment
- [ ] Add persistent user preferences/favorites
- [ ] Add monitoring for external provider failures

## Main technical risks

| Risk | Current mitigation | Next step |
|---|---|---|
| External API outage | Optional providers degrade independently | Add retries/cache and provider health metrics |
| API rate limits | Limited route sampling | Add explicit caching and quotas |
| Model/version mismatch | Pinned scikit-learn and LightGBM dependencies | Store full training environment metadata |
| Historical traffic limitations | Optional TomTom live enrichment | Validate with more current traffic datasets |
| Secret leakage | `.env` excluded from Git and `.env.example` provided | Use a secret manager for deployment |

## Definition of a successful demo

A successful run should load the backend models, generate route alternatives, return route scores, display the candidates in the UI, and show `status: ok` at `/health`. Optional TomTom, PredictHQ, and OpenAI features depend on their API keys and are not required for the core historical traffic ML pipeline to load.
