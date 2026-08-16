# MATTERS

AI-powered urban mobility and route intelligence for Los Angeles.

MATTERS compares multiple route candidates and combines routing, historical traffic prediction, optional real-time traffic, weather, holidays, events, and accident-risk estimation to recommend a better trip plan. The frontend is a browser-based Leaflet dashboard and the backend is a FastAPI service.

## What is included

- Multi-route comparison with up to 3 route candidates
- Historical traffic prediction using METR-LA sensor data
- Optional TomTom real-time traffic enrichment
- Weather-aware route context using Open-Meteo
- US holiday context using Nager.Date
- Optional PredictHQ event context
- Accident severity model using LightGBM
- Route scoring and recommendation
- Arrival-time recommendation
- Optional OpenAI explanation/chat layer
- Interactive Leaflet map UI

## Project structure

```text
MATTERS/
├── backend/                 FastAPI backend, providers, engines and ML models
├── dataset/                 METR-LA and contextual datasets
├── docs/                    Architecture and project documentation
├── frontend/
│   └── MATTERS.htm          Main UI
├── assets/                  Frontend media assets
├── .env.example             API key template
├── requirements.txt         Python dependencies
├── setup_windows.bat        One-time Windows setup
├── run_backend.bat          Start FastAPI only
├── run_ui.bat               Start the frontend server only
├── run_all.bat              Start backend + UI
└── verify_setup.py          Dependency/model diagnostic
```

## Requirements

- Python 3.11 or newer
- Internet connection for external APIs and map tiles
- Windows instructions are provided below; macOS/Linux can use the equivalent Python commands

The bundled scikit-learn models were serialized with scikit-learn 1.8.0, so the project intentionally pins that version in `requirements.txt` for compatibility.

## Quick start on Windows

### 1. Extract and open the project

Extract the ZIP and open the `MATTERS` folder in VS Code.

### 2. Run the one-time setup

Double-click:

```text
setup_windows.bat
```

Or run it from the VS Code terminal:

```bat
setup_windows.bat
```

The script creates `.venv`, installs the required Python packages, and creates `.env` from `.env.example` if needed.

### 3. Configure API keys

Open `.env` and add your keys:

```env
ORS_API_KEY=your_openrouteservice_key
TOMTOM_API_KEY=
EVENTS_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
```

`ORS_API_KEY` is required by the current routing provider. TomTom, PredictHQ, and OpenAI are optional. If an optional key is missing, the corresponding enhancement is disabled while the rest of the backend can still run.

### 4. Start the project

Run:

```bat
run_all.bat
```

Then open:

- UI: `http://127.0.0.1:5500/MATTERS.htm`
- Backend health: `http://127.0.0.1:8000/health`
- FastAPI docs: `http://127.0.0.1:8000/docs`

## Manual start

If you prefer to run each service yourself, create/activate the virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the backend from the project root:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, start the UI:

```powershell
cd frontend
python -m http.server 5500 --bind 127.0.0.1
```

Open `http://127.0.0.1:5500/MATTERS.htm`.

## Verify the setup

Run:

```powershell
python verify_setup.py
```

This checks the Python version, required packages, API-key configuration, and whether the bundled traffic and accident ML models can be loaded.

## Main backend endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Basic backend status |
| GET | `/health` | Traffic, event and model health status |
| GET | `/events-debug` | PredictHQ configuration check |
| POST | `/test` | Main route analysis and scoring |
| POST | `/arrival-recommendation` | Find a practical departure plan for a target arrival time |
| POST | `/chat` | Optional AI explanation of an already-computed route recommendation |

Interactive request/response schemas are available at `http://127.0.0.1:8000/docs` after the backend starts.

## Data and AI notes

The traffic ML component uses the METR-LA dataset and bundled Extra Trees + HistGradientBoosting models to estimate short-horizon traffic speed from historical sensor patterns and contextual features. This historical ML signal can be enriched with live TomTom traffic when a `TOMTOM_API_KEY` is configured.

The accident-risk component uses a bundled LightGBM multiclass model. The project includes the trained model files, so training notebooks are not required just to run the application.

## External services

| Service | Used for | API key |
|---|---|---|
| OpenRouteService | Primary route generation and alternatives | Required |
| OSRM | Route fallback/alternative source | No |
| Open-Meteo | Weather context | No |
| Nager.Date | US holiday context | No |
| TomTom | Real-time traffic enrichment | Optional |
| PredictHQ | Route-aware event context | Optional |
| OpenAI API | Recommendation explanation/chat | Optional |
| OpenStreetMap / Leaflet | Map display | No project key |

## Troubleshooting

### `ModuleNotFoundError: No module named 'lightgbm'`

Install the complete requirements file inside the project environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### The UI shows `NetworkError when attempting to fetch resource`

Make sure the backend is running and that `http://127.0.0.1:8000/health` opens successfully in the browser.

### Route analysis says `ORS_API_KEY is missing`

Copy `.env.example` to `.env`, add a valid `ORS_API_KEY`, and restart the backend.

### The backend runs but optional features are unavailable

Check `/health`. TomTom, PredictHQ, and OpenAI features require their corresponding keys in `.env`.

## Security

Do not commit or send real API keys inside the project ZIP. Keep them only in `.env`. The repository ignores `.env` and includes `.env.example` as the safe template.

## Documentation

Additional architecture notes and diagrams are available in the `docs/` directory.
