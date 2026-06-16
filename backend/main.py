"""
UDIARS — Unified Disaster Intelligence and Adaptive Response System
FastAPI backend: California multi-hazard POC

Endpoints:
  GET  /health          — data source health status
  GET  /mhrm            — Multi-Hazard Risk Map (GeoJSON)
  GET  /hazards         — current active hazard states (all 3 types)
  GET  /route           — primary + 2 alternate routes
  GET  /economic        — infrastructure damage / economic impact report
  POST /demo/start      — activate demo flood scenario on US-101 LA
  POST /demo/stop       — deactivate demo mode
  GET  /demo/status     — current demo state
  WS   /ws/updates      — WebSocket pushing MHRM updates every 60 s
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("udiars")

# ── APScheduler ──────────────────────────────────────────────────────────────
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Data sources ─────────────────────────────────────────────────────────────
from data_sources import (
    USGSNWISClient,
    NOAAMRMSClient,
    NASAFIRMSClient,
    USGSEarthquakeClient,
    OpenMeteoClient,
)

# ── ML models ────────────────────────────────────────────────────────────────
from models import FloodModel, WildfireModel, SeismicModel

# ── Engines ──────────────────────────────────────────────────────────────────
from engines import CompoundHazardEngine, RoutingEngine, EconomicImpactEngine

# ═════════════════════════════════════════════════════════════════════════════
# Global application state
# ═════════════════════════════════════════════════════════════════════════════

class AppState:
    # Data clients
    usgs_nwis    = USGSNWISClient()
    noaa_mrms    = NOAAMRMSClient()
    nasa_firms   = NASAFIRMSClient()
    usgs_eq      = USGSEarthquakeClient()
    open_meteo   = OpenMeteoClient()

    # Raw data cache
    gauge_readings:  list[dict] = []
    rainfall_data:   list[dict] = []
    fire_detections: list[dict] = []
    weather_data:    list[dict] = []
    earthquakes:     list[dict] = []

    # ML models
    flood_model:    FloodModel    = FloodModel()
    wildfire_model: WildfireModel = WildfireModel()
    seismic_model:  SeismicModel  = SeismicModel()

    # Engines
    hazard_engine:   Optional[CompoundHazardEngine] = None
    routing_engine:  RoutingEngine  = RoutingEngine()
    economic_engine: Optional[EconomicImpactEngine] = None

    # Current outputs
    mhrm:            dict = {"type": "FeatureCollection", "features": [], "metadata": {}}
    hazard_summary:  dict = {}
    economic_report: dict = {}

    # WebSocket clients
    ws_clients: list[WebSocket] = []

    # Demo mode
    demo_state: dict = {
        "active": False,
        "scenario": None,
        "started_at": None,
        "description": "",
        "alerts": [],
    }

    # Scheduler
    scheduler: Optional[AsyncIOScheduler] = None

    # Timestamps
    last_data_refresh:   Optional[datetime] = None
    last_mhrm_update:    Optional[datetime] = None
    startup_complete:    bool = False


state = AppState()

# ═════════════════════════════════════════════════════════════════════════════
# Core refresh cycle
# ═════════════════════════════════════════════════════════════════════════════

async def refresh_all_data():
    """Fetch all data sources in parallel, update MHRM, push via WebSocket."""
    logger.info("Starting data refresh cycle …")
    try:
        # Parallel data fetch
        results = await asyncio.gather(
            state.usgs_nwis.fetch(),
            state.noaa_mrms.fetch(),
            state.nasa_firms.fetch(),
            state.usgs_eq.fetch(),
            state.open_meteo.fetch(),
            return_exceptions=True,
        )

        # Unpack — replace exceptions with last-known or empty list
        def safe(val, fallback):
            return val if not isinstance(val, Exception) else fallback

        state.gauge_readings  = safe(results[0], state.gauge_readings  or [])
        state.rainfall_data   = safe(results[1], state.rainfall_data   or [])
        state.fire_detections = safe(results[2], state.fire_detections or [])
        state.earthquakes     = safe(results[3], state.earthquakes     or [])
        state.weather_data    = safe(results[4], state.weather_data    or [])

        state.last_data_refresh = datetime.utcnow()

        # Recompute MHRM
        state.mhrm = state.hazard_engine.update(
            gauge_readings  = state.gauge_readings,
            rainfall_data   = state.rainfall_data,
            fire_detections = state.fire_detections,
            weather_data    = state.weather_data,
            earthquakes     = state.earthquakes,
            demo_state      = state.demo_state,
        )
        state.last_mhrm_update = datetime.utcnow()

        # Apply hazard weights to routing graph
        state.routing_engine.apply_mhrm(state.mhrm)

        # Rebuild economic report
        state.economic_report = state.economic_engine.compute_report(
            mhrm        = state.mhrm,
            earthquakes = state.earthquakes,
            demo_state  = state.demo_state,
        )

        # Build hazard summary
        state.hazard_summary = _build_hazard_summary()

        # Check demo pre-emptive trigger
        if state.demo_state["active"]:
            _update_demo_alerts()

        # Broadcast to WebSocket clients
        await _broadcast_update()

        logger.info(
            "Refresh complete: %d fire detections, %d earthquakes, %d road segments",
            len(state.fire_detections),
            len(state.earthquakes),
            len(state.mhrm.get("features", [])),
        )
    except Exception as exc:
        logger.error("Refresh cycle error: %s", exc, exc_info=True)


def _build_hazard_summary() -> dict:
    features = state.mhrm.get("features", [])
    if not features:
        return {}

    flood_probs     = [f["properties"]["flood_probability"]    for f in features]
    wf_scores       = [f["properties"]["wildfire_zone_score"]  for f in features]
    seismic_probs   = [f["properties"]["seismic_shaking_prob"] for f in features]
    hazard_penalties= [f["properties"]["hazard_penalty"]       for f in features]

    def pct(vals, threshold):
        return round(100 * sum(1 for v in vals if v >= threshold) / max(len(vals), 1), 1)

    return {
        "flood": {
            "max_probability":      round(max(flood_probs), 3),
            "avg_probability":      round(sum(flood_probs) / len(flood_probs), 3),
            "high_risk_segments":   sum(1 for v in flood_probs if v >= 0.65),
            "active_gauges":        len(state.gauge_readings),
            "data_source":          "USGS NWIS + NOAA MRMS",
            "is_live":              state.usgs_nwis.status.available,
        },
        "wildfire": {
            "zone_a_segments":      sum(1 for f in features if f["properties"]["wildfire_zone"] == "A"),
            "zone_b_segments":      sum(1 for f in features if f["properties"]["wildfire_zone"] == "B"),
            "zone_c_segments":      sum(1 for f in features if f["properties"]["wildfire_zone"] == "C"),
            "active_fire_detections": len(state.fire_detections),
            "data_source":          "NASA FIRMS + Open-Meteo",
            "is_live":              state.nasa_firms.available,
        },
        "seismic": {
            "max_pga_g":            max((f["properties"]["seismic_pga_g"] for f in features), default=0.0),
            "recent_earthquakes":   len(state.earthquakes),
            "significant_eqs":      sum(1 for e in state.earthquakes if e.get("magnitude", 0) >= 4.0),
            "bridges_at_risk":      len(state.economic_report.get("bridge_damage", [])),
            "data_source":          "USGS Earthquake Hazards",
            "is_live":              state.usgs_eq.available,
        },
        "compound": {
            "max_hazard_penalty":   round(max(hazard_penalties), 3),
            "critical_segments":    sum(1 for v in hazard_penalties if v >= 0.65),
            "high_segments":        sum(1 for v in hazard_penalties if 0.35 <= v < 0.65),
            "medium_segments":      sum(1 for v in hazard_penalties if 0.15 <= v < 0.35),
            "safe_segments":        sum(1 for v in hazard_penalties if v < 0.15),
        },
        "demo_mode":  state.demo_state["active"],
        "updated_at": datetime.utcnow().isoformat(),
    }


def _update_demo_alerts():
    """Generate pre-emptive alerts for demo mode flood scenario."""
    alerts = [
        {
            "severity": "immediate",
            "color": "#FF0000",
            "message": "⚠️ FLOOD RISK DETECTED — US-101 N (LA) at Stage 18.5ft and rising",
            "highway": "US-101",
            "segment": "US-101 (LA→Ventura)",
            "action": "Pre-emptive rerouting via I-405 N and I-5 N corridors activated",
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "severity": "warning",
            "color": "#FF6600",
            "message": "🚧 LA River gauge at 18.5 ft — flood stage is 12.0 ft. Rise rate: +2.8 ft/hr",
            "highway": "US-101",
            "action": "Emergency services notified. Recommend avoiding I-101 N between Cahuenga Pass and Ventura.",
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "severity": "watch",
            "color": "#FFAA00",
            "message": "📡 NOAA MRMS: 2.1 in/hr rainfall in LA Basin — flash flood watch in effect",
            "action": "Monitor Tier 2 alternate routes. Shelter-in-place advisory for low-lying areas.",
            "timestamp": datetime.utcnow().isoformat(),
        },
    ]
    state.demo_state["alerts"] = alerts


async def _broadcast_update():
    """Push MHRM update to all connected WebSocket clients."""
    if not state.ws_clients:
        return
    payload = json.dumps({
        "type":          "mhrm_update",
        "mhrm":          state.mhrm,
        "hazard_summary": state.hazard_summary,
        "demo_state":    state.demo_state,
        "timestamp":     datetime.utcnow().isoformat(),
    })
    dead = []
    for ws in state.ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.ws_clients.remove(ws)


# ═════════════════════════════════════════════════════════════════════════════
# Startup / shutdown
# ═════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("UDIARS backend starting …")

    # Train ML models (fast on synthetic data)
    logger.info("Training ML models …")
    state.flood_model.train()
    state.wildfire_model.train()
    # SeismicModel is physics-based, no training needed

    # Initialize engines
    state.hazard_engine = CompoundHazardEngine(
        state.flood_model, state.wildfire_model, state.seismic_model
    )
    state.economic_engine = EconomicImpactEngine(state.seismic_model)

    # Start graph loading in background (non-blocking)
    asyncio.create_task(state.routing_engine.load_graph_async())

    # First data refresh
    await refresh_all_data()

    # Background scheduler — refresh every 60 seconds
    state.scheduler = AsyncIOScheduler()
    interval = int(os.getenv("REFRESH_INTERVAL_SECONDS", "60"))
    state.scheduler.add_job(refresh_all_data, "interval", seconds=interval, id="refresh")
    state.scheduler.start()

    state.startup_complete = True
    logger.info("UDIARS backend ready ✓")
    yield

    # Shutdown
    if state.scheduler:
        state.scheduler.shutdown(wait=False)
    logger.info("UDIARS backend stopped")


# ═════════════════════════════════════════════════════════════════════════════
# FastAPI app
# ═════════════════════════════════════════════════════════════════════════════

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]

app = FastAPI(
    title="UDIARS — Unified Disaster Intelligence and Adaptive Response System",
    version="1.0.0-poc",
    description="California multi-hazard prediction and adaptive routing API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # widen for local POC; tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════════════
# REST Endpoints
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["System"])
async def health():
    """Status of each upstream data source and system readiness."""
    return {
        "status": "ok" if state.startup_complete else "starting",
        "data_sources": {
            "usgs_nwis": {
                "available":   state.usgs_nwis.status.available,
                "last_check":  state.usgs_nwis.status.last_check,
                "error":       state.usgs_nwis.status.error_msg or None,
            },
            "noaa_mrms": {
                "available":   state.noaa_mrms.available,
                "last_check":  state.noaa_mrms.last_check,
                "error":       state.noaa_mrms.error_msg or None,
            },
            "nasa_firms": {
                "available":   state.nasa_firms.available,
                "api_key_set": bool(state.nasa_firms.api_key),
                "last_check":  state.nasa_firms.last_check,
                "error":       state.nasa_firms.error_msg or None,
            },
            "usgs_earthquake": {
                "available":   state.usgs_eq.available,
                "last_check":  state.usgs_eq.last_check,
                "error":       state.usgs_eq.error_msg or None,
            },
            "open_meteo": {
                "available":   state.open_meteo.available,
                "last_check":  state.open_meteo.last_check,
                "error":       state.open_meteo.error_msg or None,
            },
        },
        "routing_engine": {
            "graph_loaded":   state.routing_engine.graph_loaded,
            "load_error":     state.routing_engine.load_error or None,
        },
        "ml_models": {
            "flood":    state.flood_model._trained,
            "wildfire": state.wildfire_model._trained,
            "seismic":  state.seismic_model._trained,
        },
        "last_data_refresh":  state.last_data_refresh,
        "last_mhrm_update":   state.last_mhrm_update,
        "ws_clients_connected": len(state.ws_clients),
        "demo_mode":          state.demo_state["active"],
    }


@app.get("/mhrm", tags=["Hazards"])
async def get_mhrm():
    """Current Multi-Hazard Risk Map as GeoJSON FeatureCollection."""
    if not state.mhrm.get("features"):
        raise HTTPException(503, "MHRM not yet computed — please retry in a few seconds")
    return state.mhrm


@app.get("/hazards", tags=["Hazards"])
async def get_hazards():
    """Active hazard state summary for all three hazard types."""
    if not state.hazard_summary:
        raise HTTPException(503, "Hazard data not yet available")
    return state.hazard_summary


@app.get("/route", tags=["Routing"])
async def get_route(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lng: float = Query(..., description="Origin longitude"),
    dest_lat:   float = Query(..., description="Destination latitude"),
    dest_lng:   float = Query(..., description="Destination longitude"),
):
    """
    Compute primary route + 2 independent alternate corridors.
    Returns GeoJSON FeatureCollection with hazard-penalized edge weights applied.
    Pre-emptive trigger fires if flood_prob > 0.65 on any primary segment.
    """
    # Validate California bounding box
    for name, lat, lon in [
        ("origin", origin_lat, origin_lng),
        ("destination", dest_lat, dest_lng),
    ]:
        if not (32.5 <= lat <= 42.1 and -124.5 <= lon <= -114.1):
            raise HTTPException(
                400,
                f"{name} coordinates ({lat}, {lon}) are outside California bounds"
            )

    routes = state.routing_engine.compute_routes(origin_lat, origin_lng, dest_lat, dest_lng)

    # Inject demo alerts if active
    if state.demo_state["active"]:
        routes["demo_alerts"] = state.demo_state.get("alerts", [])
        # Override primary route hazard to trigger pre-emptive alert
        for feat in routes.get("features", []):
            if feat["properties"]["route_type"] == "primary":
                feat["properties"]["pre_emptive_trigger"] = True
                feat["properties"]["max_hazard_penalty"]  = 0.92
                feat["properties"]["alert_message"] = (
                    "⚠️ DEMO: Flood risk detected on US-101 N — "
                    "rerouting via I-405 N / I-5 alternate corridors"
                )
                feat["properties"]["color"] = "#FF0000"

    return routes


@app.get("/economic", tags=["Economic Impact"])
async def get_economic():
    """
    Infrastructure damage estimates and economic loss projections.
    Based on HAZUS-MH simplified fragility curves applied to affected road segments.
    """
    if not state.economic_report:
        raise HTTPException(503, "Economic report not yet available")
    return state.economic_report


# ─── Demo mode ───────────────────────────────────────────────────────────────

@app.post("/demo/start", tags=["Demo"])
async def demo_start():
    """
    Activate demo mode: simulates live flood event on US-101 in Los Angeles.
    Injects elevated stage / rainfall into the flood model, triggers pre-emptive
    rerouting, and broadcasts alerts via WebSocket.
    """
    state.demo_state.update({
        "active":      True,
        "scenario":    "LA_101_FLOOD",
        "started_at":  datetime.utcnow().isoformat(),
        "description": (
            "Simulated flash flood on US-101 (Hollywood Freeway) in Los Angeles. "
            "LA River gauge at 18.5 ft (flood stage 12 ft), rise rate 2.8 ft/hr. "
            "NOAA MRMS rainfall: 2.1 in/hr. Pre-emptive rerouting via I-405/I-5 activated."
        ),
    })
    # Force immediate data refresh to propagate demo state
    await refresh_all_data()
    return {
        "status":  "demo_active",
        "scenario": state.demo_state["scenario"],
        "message": "Demo flood scenario activated. Watch for pre-emptive trigger on US-101.",
    }


@app.post("/demo/stop", tags=["Demo"])
async def demo_stop():
    """Deactivate demo mode and revert to live data."""
    state.demo_state.update({
        "active":      False,
        "scenario":    None,
        "started_at":  None,
        "description": "",
        "alerts":      [],
    })
    await refresh_all_data()
    return {"status": "demo_inactive", "message": "Demo mode stopped. Live data restored."}


@app.get("/demo/status", tags=["Demo"])
async def demo_status():
    """Current demo mode state."""
    return state.demo_state


# ─── Force refresh ────────────────────────────────────────────────────────────

@app.post("/refresh", tags=["System"])
async def force_refresh():
    """Trigger an immediate data refresh cycle (outside the 60-second schedule)."""
    await refresh_all_data()
    return {
        "status":    "refreshed",
        "timestamp": state.last_mhrm_update,
        "n_segments": len(state.mhrm.get("features", [])),
    }


# ═════════════════════════════════════════════════════════════════════════════
# WebSocket endpoint
# ═════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    """
    WebSocket endpoint: pushes MHRM updates every 60 seconds.
    Also sends an immediate snapshot on connection.
    Client can send {"type": "ping"} to check connectivity.
    """
    await websocket.accept()
    state.ws_clients.append(websocket)
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket client connected: %s (total: %d)", client_host, len(state.ws_clients))

    try:
        # Send initial snapshot immediately on connect
        await websocket.send_text(json.dumps({
            "type":          "initial_snapshot",
            "mhrm":          state.mhrm,
            "hazard_summary": state.hazard_summary,
            "demo_state":    state.demo_state,
            "health": {
                "startup_complete": state.startup_complete,
                "last_refresh":     state.last_data_refresh.isoformat() if state.last_data_refresh else None,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }))

        # Keep-alive loop — actual broadcasts happen in refresh_all_data()
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(msg)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type":      "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                        "demo_active": state.demo_state["active"],
                    }))
                elif data.get("type") == "request_refresh":
                    await refresh_all_data()
            except asyncio.TimeoutError:
                # Send heartbeat so client knows connection is alive
                await websocket.send_text(json.dumps({
                    "type":      "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                }))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", client_host)
    except Exception as exc:
        logger.warning("WebSocket error for %s: %s", client_host, exc)
    finally:
        if websocket in state.ws_clients:
            state.ws_clients.remove(websocket)


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=False,
        log_level="info",
    )
