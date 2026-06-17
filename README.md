# UDIARS — Unified Disaster Intelligence and Adaptive Response System
### Multi-Hazard, Multi-State Proof of Concept (California · New York · New Jersey)

Full-stack flood / wildfire / seismic prediction and pre-emptive adaptive routing,
implementing the six-step method and three-tier interface described in the UDIARS
provisional patent specification. See **[Patent Claims Coverage](#patent-claims-coverage)**
below for how each of the nine claims maps to running code.

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
| GET | `/regions` | Supported state bounding boxes (CA / NY / NJ) for map sync |
| GET | `/mhrm?region=` | Multi-Hazard Risk Map (GeoJSON FeatureCollection), optionally scoped to `california` or `njny` |
| GET | `/hazards?region=` | Active hazard summary for all 3 types, region-scoped |
| GET | `/facilities?region=` | Shelters + hospitals, region-scoped |
| GET | `/route?origin_lat=&origin_lng=&dest_lat=&dest_lng=&region=` | Primary + 2 independent alternate routes — never returns 404/500; falls back to static region-appropriate JSON on any routing-engine error |
| GET | `/economic?region=` | HAZUS bridge damage + highway closure costs |
| POST | `/demo/start` / `/demo/stop` / `GET /demo/status` | Legacy single-scenario LA US-101 flood demo |
| POST | `/demo/flood` | California flood demo (US-101 Ventura→SLO, P(flood)=0.78) |
| POST | `/demo/flood/njny` | NJ/NY flood demo (US-1 near New Brunswick, Raritan River gauge, P(flood)=0.82) |
| POST | `/demo/flood/all` | Activates both CA and NJ/NY demo scenarios simultaneously |
| POST | `/demo/zone/{a\|b\|c\|clear}` | Force a wildfire zone override for demo purposes (auto-clears after 60s) |
| POST | `/refresh` | Force immediate data refresh |
| WS | `/ws/updates` | Live MHRM push every 60 seconds, plus heartbeats and live pre-emptive trigger status |

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

## Patent Claims Coverage

The provisional specification's six-step method (FIG. 11) and nine claims map to this
codebase as follows. All references are to the running POC, not aspirational design.

| Claim / Step | Patent Requirement | Implementation |
|---|---|---|
| Step 1 — Real-time ingestion | Continuously ingest hydrological, meteorological, fire, and seismic data | `data_sources/` — USGS NWIS (gauges), NOAA MRMS proxy via Open-Meteo (rainfall), NASA FIRMS (fire detections), USGS Earthquake Hazards (seismic events), Open-Meteo (wind/temp/humidity). All five run in parallel each refresh cycle (`main.py: refresh_all_data`), each with automatic synthetic-data fallback so the system never blocks on an unavailable upstream API. |
| Step 2 — ML-predicted future hazard conditions | Predict hazard probability ahead of physical onset, not just current state | `models/flood_model.py` (Random Forest, 150 trees), `models/wildfire_model.py` (XGBoost / GradientBoosting fallback), `models/seismic_model.py` (physics-based Atkinson-Boore 2003 PGA estimate). `engines/compound_hazard.py` layers a simplified LSTM-trend approximation on top of the RF output (Fix 8.2) and emits 30/60/90-minute forward probability horizons per segment (`flood_prob_30/60/90`). |
| Step 3 — Multi-Hazard Risk Map (MHRM) fusion | Combine flood, wildfire, and seismic outputs into one composite risk surface | `engines/compound_hazard.py: CompoundHazardEngine.update()` — computes `HazardPenalty = max(flood_prob, wildfire_zone_score, seismic_shaking_prob)` per road segment across all three states and serializes the result as a GeoJSON FeatureCollection (`GET /mhrm`). Each feature also reports `dominant_hazard` (flood/wildfire/seismic/compound) per Fix 7. |
| Step 4 — Dynamic edge weighting | Apply hazard- and traffic-aware weights to the road network | `w(e,t) = T_nominal × (1 + 0.5·TrafficDensity(e,t)) + 5.0·HazardPenalty(e,t)` implemented exactly as specified in `compound_hazard.py` (`ALPHA_TRAFFIC=0.5`, `BETA_HAZARD=5.0`). `traffic_density_for_hour()` is a time-of-day proxy (Fix 8.1) standing in for live traffic feeds, which are out of POC scope. |
| Step 5 — Primary + 2 independent alternate routes | Pre-compute a primary route and at least two independent alternates before a closure occurs | `engines/routing_engine.py` (OSMnx/Dijkstra over LA + Bay Area graph, straight-line fallback elsewhere) and the `/route` endpoint's static fallback payloads (`_CALIFORNIA_FALLBACK`, `_NJNY_FALLBACK`) each return `primary`, `alternate1`, `alternate2`, with alternates flagged `independent_of_primary: true`. |
| Step 6 — Pre-emptive transmission before closure | Notify and reroute before the hazard physically closes the road | Two independent trigger paths: (a) demo-forced triggers via `/demo/flood`, `/demo/flood/njny`, `/demo/flood/all` that set `flood_prob ≥ 0.65` and `edge_weight=9.5` on a named segment with a recorded `trigger_time_utc`; (b) `_update_live_trigger()` in `main.py`, which scans the live (non-demo) MHRM every refresh cycle for any segment crossing the same 0.65 threshold and surfaces it via `live_pre_emptive_trigger` in `/hazards` and the WebSocket broadcast — i.e. the system can also fire pre-emptively from real (or synthetic-fallback) data, not only the demo button. |
| Claim — Three-tier interface | Distinct views for driver / first responder / emergency manager | `frontend/src/components/Sidebar.jsx` + `TIER_INFO` in `constants/appData.js`: Tier 1 (single route, plain-language status), Tier 2 (all routes, hazard scores, shelter/hospital), Tier 3 (full per-segment MHRM + economic impact dashboard). |
| Claim — Explainability | Surface the contributing factors behind a hazard prediction | Per-segment `shap_top_features` (Fix 9) ranks `stage_rate_ft_hr`, `rainfall_1hr_in`, and `soil_moisture_index` by normalized contribution weight; rendered in the Tier 2/3 sidebar as `SHAPBreakdown`. |
| Claim — Multi-region generalizability | Method is not limited to a single geography | Same pipeline runs over California, New York, and New Jersey segments concurrently (`CA_HIGHWAY_SEGMENTS` / `NY_HIGHWAY_SEGMENTS` / `NJ_HIGHWAY_SEGMENTS` in `compound_hazard.py`), with region-scoped REST filtering (`?region=california` / `?region=njny`) on `/mhrm`, `/hazards`, `/facilities`, and `/economic`. |

**Known POC-scope simplifications** (disclosed, not hidden): traffic density is a static
time-of-day curve rather than a live feed; the "LSTM" trend adjustment is a rule-based
multiplier on stage rate rather than a trained recurrent network; OSMnx road graphs are
loaded only for LA + SF Bay Area, with a straight-line interpolation fallback elsewhere;
elevation is a coastal-distance heuristic rather than SRTM lookup. None of these affect
claim coverage — each claim's *mechanism* is implemented end-to-end — but a production
system would replace these proxies with their full-fidelity counterparts (see Notes for
Production below).

---

## Notes for Production

- Replace SQLite caching with PostgreSQL + PostGIS
- Add authentication to `/demo/start` and `/refresh`
- Use a proper SRTM elevation API for precise elevation data
- OSMnx graph download for full California takes ~10 minutes; pre-cache it
- For FHWA NBI bridge data, download from https://www.fhwa.dot.gov/bridge/nbi/
- Wildfire FRP-weighted spread modeling needs WRF-Fire or FARSITE integration
- Seismic ShakeAlert real-time feed requires USGS ShakeAlert partner agreement
