# MATTERS - Project Overview

## Executive Summary

MATTERS is an AI-assisted urban mobility platform for Los Angeles. It compares multiple route candidates and combines route geometry, historical traffic prediction, optional live traffic, weather, holidays, nearby events, and accident-risk estimation to support better travel decisions.

The system is designed as a decision-support application rather than a replacement for a commercial navigation service. Its main academic contribution is the integration of several heterogeneous mobility signals into one route-scoring pipeline and interactive dashboard.

## Problem Statement

Traffic conditions are influenced by more than road distance alone. Time of day, historical congestion patterns, weather, holidays, live traffic, events, and safety conditions can all change the practical quality of a route. A route that is shortest in distance is not always the best option for a specific departure time and context.

## Current Solution

MATTERS generates up to three route candidates, enriches them with contextual data, estimates traffic conditions, evaluates accident risk, and ranks the routes using a route-scoring engine. The final recommendation is visualized in a Leaflet-based dashboard and can optionally be explained in natural language using the OpenAI API.

## Current Features

- Up to three route candidates
- METR-LA historical traffic ML prediction
- Optional TomTom real-time traffic enrichment
- Weather-aware route analysis using Open-Meteo
- US public-holiday context using Nager.Date
- Optional PredictHQ event-aware route context
- LightGBM accident-severity inference
- Route scoring and recommendation
- ETA and route comparison
- Arrival-time recommendation
- Interactive Leaflet map
- Optional AI explanation/chat

## Machine Learning Components

### Traffic prediction

The traffic pipeline uses METR-LA sensor data and bundled scikit-learn models:

- ExtraTreesRegressor
- HistGradientBoostingRegressor

The bundled scikit-learn models were serialized with version 1.8.0.

### Accident risk

The accident component uses a bundled LightGBM multiclass model that predicts accident severity from location, weather and road-context features.

## Technology Stack

- Python 3.11+
- FastAPI + Uvicorn
- NumPy / Pandas / PyTables
- scikit-learn
- LightGBM
- HTML / CSS / JavaScript
- Leaflet + OpenStreetMap
- OpenRouteService + OSRM
- Open-Meteo
- Nager.Date
- Optional TomTom Traffic
- Optional PredictHQ Events
- Optional OpenAI API

## Project Scope

The current version is a functional integrated prototype intended for academic demonstration and experimentation. Historical METR-LA traffic prediction is not equivalent to complete live citywide traffic sensing. When configured, TomTom provides an additional real-time traffic signal.

## Future Improvements

- Better calibration of route-scoring weights
- Larger route sensor coverage and confidence estimation
- More rigorous model evaluation on held-out periods
- Persistent user accounts and saved preferences
- Production deployment configuration
- Automated API integration tests
- Better caching and rate-limit handling for external providers
