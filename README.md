# UDIARS — Unified Disaster Intelligence and Adaptive Response System
### California Multi-Hazard POC

Full-stack flood / wildfire / seismic prediction and adaptive routing for California.

---

## Architecture

```
udiars/
├── backend/                 ← Python 3.11 / FastAPI
│   ├── main.py              ← App entry point, all endpoints, WebSocket, scheduler
│   ├── requirements.txt
│   ├── .env.example
│   ├── data_sources/        ← Live API clients (USGS, NOAA, NASA, USGS-EQ, Open-Meteo)
│   ├── models/              ← ML models (Flood: RF, Wildfire: XGBoost, Seismic: physics)
│   └── engines/             ← Compound hazard, routing (OSMnx/Dijkstra), economic (HAZUS)
└── frontend/                ← React 18 / Leaflet
    ├── src/App.jsx          ← Root layout
    ├── src/components/      ← MapView, Sidebar (Tiers 1/2/3), ControlPanel, AlertBanner
    └── src/hooks/           ← useWebSocket (auto-reconnect), useHazardData (REST + WS)
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+ / npm 9+

---

## Backend Setup

```bash
cd udiars/backend

# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — at minimum set NASA_FIRMS_API_KEY (free registration below)
# All other keys are optional; the system falls back to synthetic data automatically.

# 4. Start backend
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at **http://localhost:8000**
Interactive API docs at **http://localhost:8000/docs**

### Optional: NASA FIRMS API Key
Register free at https://firms.modaps.eosdis.nasa.gov/api/
Set `NASA_FIRMS_API_KEY=your_key` in `.env`
Without it, wildfire data uses realistic synthetic fire detections.

---

## Frontend Setup

```bash
cd udiars/frontend

# 1. Install dependencies
npm install

# 2. Start dev server
npm start
```

Frontend runs at **http://localhost:3000**

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Data source status + system readiness |
| GET | `/mhrm` | Multi-Hazard Risk Map (GeoJSON FeatureCollection) |
| GET | `/hazards` | Active hazard summary for all 3 types |
| GET | `/route?origin_lat=&origin_lng=&dest_lat=&dest_lng=` | Primary + 2 alternate routes |
| GET | `/economic` | HAZUS bridge damage + highway closure costs |
| POST | `/demo/start` | Activate LA US-101 flood demo scenario |
| POST | `/demo/stop` | Deactivate demo mode |
| GET | `/demo/status` | Current demo state |
| POST | `/refresh` | Force immediate data refresh |
| WS | `/ws/updates` | Live MHRM push every 60 seconds |

---

## Demo Mode — LA US-101 Flood Scenario

Demo mode simulates a live flash flood event on US-101 (Hollywood Freeway) in Los Angeles:

- **LA River gauge:** 18.5 ft (flood stage 12.0 ft) · Rise rate +2.8 ft/hr
- **NOAA MRMS rainfall:** 2.1 in/hr
- **Pre-emptive trigger fires** for any route using US-101 between downtown and Ventura
- **Alternate routes** via I-405 N and I-5 N activate automatically
- **Alert banner** shows IMMEDIATE / WARNING / WATCH tier alerts

**To activate:**

Option A — UI: Click **"🎬 Demo: LA-101 Flood"** in the control panel

Option B — API:
```bash
curl -X POST http://localhost:8000/demo/start
```

**To stop:**
```bash
curl -X POST http://localhost:8000/demo/stop
```

---

## Three-Tier Interface

| Tier | Audience | What you see |
|------|----------|-------------|
| **T1 · Driver** | General public | Single route card, plain language alert, ETA to safety |
| **T2 · First Responder** | Emergency services | All 3 routes with hazard scores, shelter/hospital locations |
| **T3 · Emergency Manager** | EOC staff | Full MHRM per-segment data, economic damage dashboard |

Switch tiers with the T1 / T2 / T3 buttons in the sidebar header.

---

## Data Sources

| Source | Data | Fallback |
|--------|------|---------|
| [USGS NWIS](https://waterservices.usgs.gov/nwis/) | Stream gauge stage + rise rate | Synthetic (10 CA gauges) |
| [Open-Meteo](https://api.open-meteo.com/) | Rainfall accumulation (MRMS proxy) | Synthetic (10 CA points) |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/) | Active fire detections (VIIRS) | Synthetic (~15 detections) |
| [USGS Earthquakes](https://earthquake.usgs.gov/fdsnws/event/1/) | M2.5+ events, last 7 days | Synthetic (8 events) |
| [Open-Meteo](https://api.open-meteo.com/) | Wind speed, temp, humidity | Synthetic (10 CA points) |
| [OSMnx](https://osmnx.readthedocs.io/) | LA + SF Bay Area road graph | Synthetic 14-node graph |

All clients include automatic fallback — the system runs fully offline.

---

## ML Models

| Model | Algorithm | Features | Training Data |
|-------|-----------|----------|--------------|
| Flood | Random Forest (150 trees) | stage_ft, stage_rate, rainfall_1hr, rainfall_6hr, soil_moisture_index, elevation | 5,000 synthetic CA samples |
| Wildfire | XGBoost multi-class | distance_to_fire, wind_speed, temperature, humidity, FRP, NDVI, elevation | 6,000 synthetic CA samples |
| Seismic | Physics-based (HAZUS) | PGA (Atkinson-Boore 2003), distance to fault, depth | NSHM-2023 fragility curves |

---

## Routing Engine

Edge weight formula:
```
w(e,t) = T_nominal × (1 + 0.5 × TrafficDensity) + 5.0 × HazardPenalty

HazardPenalty = max(flood_prob, wildfire_zone_score, seismic_shaking_prob)
```

Pre-emptive trigger: if `flood_prob > 0.65` on any primary route segment → immediate Dijkstra recalculation.

Background scheduler recalculates all routes every **60 seconds** via APScheduler.

---

## WebSocket Live Updates

The frontend connects to `ws://localhost:8000/ws/updates`.

Message types received:
- `initial_snapshot` — full MHRM + hazard summary on connect
- `mhrm_update` — broadcast every 60 seconds after each data refresh
- `heartbeat` — sent every 30 seconds if no update
- `pong` — response to client ping

Client can send:
- `{"type": "ping"}` — get pong + demo status
- `{"type": "request_refresh"}` — trigger immediate data refresh

The `useWebSocket` hook auto-reconnects with exponential backoff (3s → max 30s).

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NASA_FIRMS_API_KEY` | _(empty)_ | NASA FIRMS MAP_KEY (optional) |
| `APP_HOST` | `0.0.0.0` | Backend bind host |
| `APP_PORT` | `8000` | Backend port |
| `REFRESH_INTERVAL_SECONDS` | `60` | Data refresh cadence |
| `OSMNX_CACHE_DIR` | `./cache/osmnx` | OSMnx tile cache directory |
| `DEMO_MODE` | `false` | Start in demo mode |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |

---

## Notes for Production

- Replace SQLite caching with PostgreSQL + PostGIS
- Add authentication to `/demo/start` and `/refresh`
- Use a proper SRTM elevation API for precise elevation data
- OSMnx graph download for full California takes ~10 minutes; pre-cache it
- For FHWA NBI bridge data, download from https://www.fhwa.dot.gov/bridge/nbi/
- Wildfire FRP-weighted spread modeling needs WRF-Fire or FARSITE integration
- Seismic ShakeAlert real-time feed requires USGS ShakeAlert partner agreement
