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
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# ── Supported state regions ───────────────────────────────────────────────────
# Bounding boxes / map defaults for all supported states. CA remains the default.
STATE_BOUNDS = {
    "CA": {
        "name": "California",
        "min_lat": 32.5, "max_lat": 42.1,
        "min_lon": -124.5, "max_lon": -114.1,
        "center": [37.0, -119.5],
        "zoom": 6,
    },
    "NY": {
        "name": "New York",
        "min_lat": 40.4, "max_lat": 45.1,
        "min_lon": -79.8, "max_lon": -71.7,
        "center": [42.9, -75.5],
        "zoom": 6,
    },
    "NJ": {
        "name": "New Jersey",
        "min_lat": 38.9, "max_lat": 41.4,
        "min_lon": -75.6, "max_lon": -73.9,
        "center": [40.1, -74.7],
        "zoom": 8,
    },
}


def format_incident_time(dt_utc: datetime, region: str) -> str:
    """
    Format a UTC timestamp as a region-local display string for demo banners.
    POC simplification: fixed PT/ET offsets, no DST table.
    """
    tz_offset = -7 if region == "california" else -4  # PT vs ET (simplification, no DST table needed for POC)
    tz_label = "PT" if region == "california" else "ET"
    local = dt_utc + timedelta(hours=tz_offset)
    return f"{local.strftime('%b %d, %Y')} · {local.strftime('%I:%M %p').lstrip('0')} {tz_label}"

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
    get_facilities,
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

    # Live pre-emptive trigger (Fix 8.3) — distinct from the manual demo button
    live_trigger: dict = {"active": False}

    # Zone override for demo purposes (Fix 9) — "a"/"b"/"c" or None
    zone_override: Optional[str] = None

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

        # Apply demo zone override (Fix 9) — for demo purposes only, reports
        # every segment as being in the overridden wildfire zone.
        if state.zone_override:
            zone_label = state.zone_override.upper()
            zone_score = {"A": 1.0, "B": 0.6, "C": 0.3}.get(zone_label, 0.0)
            for feat in state.mhrm.get("features", []):
                feat["properties"]["wildfire_zone"] = zone_label
                feat["properties"]["wildfire_zone_score"] = zone_score

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

        # Live pre-emptive trigger scan (Fix 8.3) — distinguishable from the
        # manual demo button: only set when demo mode is NOT active.
        _update_live_trigger()

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


def _update_live_trigger():
    """
    Fix 8.3: scan MHRM features for any segment with flood_probability >= 0.65.
    If found AND demo mode is NOT active, set state.live_trigger active so the
    frontend can render a WATCH/WARNING banner without the demo button.
    """
    if state.demo_state.get("active"):
        state.live_trigger = {"active": False}
        return

    features = state.mhrm.get("features", [])
    hot = [f for f in features if f["properties"].get("flood_probability", 0.0) >= 0.65]
    if hot:
        top = max(hot, key=lambda f: f["properties"]["flood_probability"])
        state.live_trigger = {
            "active": True,
            "segment": top["properties"].get("name", ""),
            "flood_prob": top["properties"].get("flood_probability", 0.0),
            "detected_at": datetime.utcnow().isoformat(),
        }
    else:
        state.live_trigger = {"active": False}


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
        "live_pre_emptive_trigger": state.live_trigger,
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


@app.get("/regions", tags=["Regions"])
async def get_regions():
    """
    Supported state regions (California, New York, New Jersey) with bounding
    boxes, map center, and default zoom — kept in sync with backend validation
    so the frontend never needs to duplicate these constants.
    """
    return {
        "default": "CA",
        "regions": [
            {
                "id": state_id,
                "name": b["name"],
                "bbox": {
                    "min_lat": b["min_lat"],
                    "max_lat": b["max_lat"],
                    "min_lon": b["min_lon"],
                    "max_lon": b["max_lon"],
                },
                "center": b["center"],
                "zoom": b["zoom"],
            }
            for state_id, b in STATE_BOUNDS.items()
        ],
    }


def _region_filter_key(region: str) -> Optional[set]:
    """
    Best-effort POC-scope region filter (Fix 10.1) — not exhaustive.
    Returns a set of segment "region" tags to keep, or None to mean "no filtering"
    (i.e. return everything, matching today's default behavior).
    region == "california" -> {"CA"}; "njny"/"nj"/"ny" -> {"NJ","NY"}; anything
    else (including "all"/missing) -> None (unfiltered — never reduce existing
    functionality that currently returns all regions by default).
    """
    region = (region or "all").lower()
    if region == "california":
        return {"CA"}
    if region in ("njny", "nj", "ny"):
        return {"NJ", "NY"}
    return None


@app.get("/mhrm", tags=["Hazards"])
async def get_mhrm(region: str = "all"):
    """
    Current Multi-Hazard Risk Map as GeoJSON FeatureCollection.
    `region` is a best-effort POC-scope filter (Fix 10.1): "california" limits
    to CA segments, "njny"/"nj"/"ny" limits to NJ+NY segments, anything else
    (default "all") returns every segment — matching pre-existing behavior.
    """
    if not state.mhrm.get("features"):
        raise HTTPException(503, "MHRM not yet computed — please retry in a few seconds")

    keep = _region_filter_key(region)
    if keep is None:
        return state.mhrm

    filtered_features = [
        f for f in state.mhrm["features"]
        if f["properties"].get("region") in keep
    ]
    return {**state.mhrm, "features": filtered_features}


@app.get("/hazards", tags=["Hazards"])
async def get_hazards(region: str = "all"):
    """
    Active hazard state summary for all three hazard types.
    `region` is a best-effort POC-scope filter (Fix 10.1) — see /mhrm docstring.
    """
    if not state.hazard_summary:
        raise HTTPException(503, "Hazard data not yet available")

    summary = dict(state.hazard_summary)
    keep = _region_filter_key(region)
    if keep is not None:
        features = [
            f for f in state.mhrm.get("features", [])
            if f["properties"].get("region") in keep
        ]
        if features:
            flood_probs = [f["properties"]["flood_probability"] for f in features]
            hazard_penalties = [f["properties"]["hazard_penalty"] for f in features]
            summary = {
                **summary,
                "flood": {
                    **summary.get("flood", {}),
                    "max_probability": round(max(flood_probs), 3),
                    "avg_probability": round(sum(flood_probs) / len(flood_probs), 3),
                    "high_risk_segments": sum(1 for v in flood_probs if v >= 0.65),
                },
                "wildfire": {
                    **summary.get("wildfire", {}),
                    "zone_a_segments": sum(1 for f in features if f["properties"]["wildfire_zone"] == "A"),
                    "zone_b_segments": sum(1 for f in features if f["properties"]["wildfire_zone"] == "B"),
                    "zone_c_segments": sum(1 for f in features if f["properties"]["wildfire_zone"] == "C"),
                },
                "compound": {
                    **summary.get("compound", {}),
                    "max_hazard_penalty": round(max(hazard_penalties), 3),
                    "critical_segments": sum(1 for v in hazard_penalties if v >= 0.65),
                    "high_segments": sum(1 for v in hazard_penalties if 0.35 <= v < 0.65),
                    "medium_segments": sum(1 for v in hazard_penalties if 0.15 <= v < 0.35),
                    "safe_segments": sum(1 for v in hazard_penalties if v < 0.15),
                },
            }

    summary["live_pre_emptive_trigger"] = state.live_trigger
    return summary


@app.get("/facilities", tags=["Facilities"])
async def get_facilities_endpoint(region: str = "all"):
    """Shelters and hospitals, optionally filtered by region (Fix 11)."""
    return get_facilities(region)


# ── /route fallback payloads (Fix 5) ───────────────────────────────────────
_CALIFORNIA_FALLBACK = {
    "primary":    {"corridor": "I-5 N via Stockton", "hazard_score": 0.18, "eta_minutes": 22, "segments": ["I-5 N", "CA-99 N", "US-50 E"], "shelter": "Sacramento Convention Center", "hospital": "UC Davis Medical Center", "fuel": "Chevron - I-5 Exit 487"},
    "alternate1": {"corridor": "US-101 N via Salinas", "hazard_score": 0.31, "eta_minutes": 28, "segments": ["US-101 N", "CA-156 E", "CA-33 N"], "shelter": "Fresno Convention Center", "hospital": "Community Regional Medical Center", "fuel": "Shell - US-101 Exit 19"},
    "alternate2": {"corridor": "CA-1 N via Big Sur", "hazard_score": 0.12, "eta_minutes": 41, "segments": ["CA-1 N", "CA-46 E", "CA-33 N"], "shelter": "San Luis Obispo Shelter", "hospital": "Sierra Vista Regional Medical", "fuel": "Arco - CA-1 Morro Bay"},
}

_NJNY_FALLBACK = {
    "primary":    {"corridor": "I-287 W via Piscataway", "hazard_score": 0.14, "eta_minutes": 19, "segments": ["I-287 W", "NJ-18 N", "US-1 N"], "shelter": "Rutgers Athletic Center", "hospital": "Robert Wood Johnson University Hospital", "fuel": "Wawa - US-1 New Brunswick"},
    "alternate1": {"corridor": "NJ Turnpike N via Newark", "hazard_score": 0.22, "eta_minutes": 26, "segments": ["I-95 N", "NJ-21 N", "I-280 E"], "shelter": "Meadowlands Expo Center", "hospital": "Newark Beth Israel Medical Center", "fuel": "BP - NJ Turnpike Exit 15W"},
    "alternate2": {"corridor": "Garden State Pkwy N via Woodbridge", "hazard_score": 0.11, "eta_minutes": 34, "segments": ["GSP N", "NJ-35 N", "I-287 E"], "shelter": "Javits Center NYC", "hospital": "NYU Langone Medical Center", "fuel": "Sunoco - GSP Exit 127"},
}


def _build_route_fallback(region_key: str) -> dict:
    """Build the Fix 5 fallback payload (status 200, never raises)."""
    base = _CALIFORNIA_FALLBACK if region_key == "california" else _NJNY_FALLBACK
    out = {"status": "fallback", "region": region_key}
    for key in ("primary", "alternate1", "alternate2"):
        rec = dict(base[key])
        if key != "primary":
            rec["independent_of_primary"] = True
        out[key] = rec
    return out


@app.get("/route", tags=["Routing"])
async def get_route(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, region: str = "california"):
    """
    Compute primary route + 2 independent alternate corridors.
    This endpoint must NEVER return 404/500 (Fix 5): bbox validation is
    tolerant (logs a warning instead of raising) and any exception from the
    routing engine falls back to a static, region-appropriate JSON payload.
    Pre-emptive trigger fires if flood_prob > 0.65 on any primary segment.
    """
    region_key = "njny" if region.lower() in ("njny", "nj", "ny") else "california"

    # Validate against supported state bounding boxes (CA, NY, NJ) — tolerant.
    for name, lat, lon in [
        ("origin", origin_lat, origin_lng),
        ("destination", dest_lat, dest_lng),
    ]:
        in_any_state = any(
            b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]
            for b in STATE_BOUNDS.values()
        )
        if not in_any_state:
            logger.warning(
                "%s coordinates (%s, %s) are outside supported regions — "
                "proceeding anyway (Fix 5: /route never errors on bbox validation)",
                name, lat, lon,
            )

    computed_at = datetime.utcnow().isoformat()
    origin_echo = {"lat": origin_lat, "lng": origin_lng}
    dest_echo = {"lat": dest_lat, "lng": dest_lng}

    try:
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
            for feat in routes.get("features", []):
                if feat["properties"]["route_type"] != "primary":
                    feat["properties"]["independent_of_primary"] = True

        routes.setdefault("origin", origin_echo)
        routes.setdefault("destination", dest_echo)
        routes["graph_loaded"] = state.routing_engine.graph_loaded
        routes["computed_at"] = routes.get("computed_at", computed_at)
        return routes
    except Exception as exc:
        logger.warning("compute_routes failed — falling back to static JSON (Fix 5): %s", exc)
        fallback = _build_route_fallback(region_key)
        fallback["graph_loaded"] = state.routing_engine.graph_loaded
        fallback["computed_at"] = computed_at
        fallback["origin"] = origin_echo
        fallback["destination"] = dest_echo
        return fallback


@app.get("/economic", tags=["Economic Impact"])
async def get_economic(region: str = "all"):
    """
    Infrastructure damage estimates and economic loss projections.
    Based on HAZUS-MH simplified fragility curves applied to affected road segments.
    `region` is a best-effort POC-scope filter (Fix 10.1): filters
    highway_closures by segment region tag if recognizable; bridge_damage
    isn't tagged with a region field today, so it is left unfiltered to
    avoid breaking existing functionality.
    """
    if not state.economic_report:
        raise HTTPException(503, "Economic report not yet available")

    keep = _region_filter_key(region)
    if keep is None:
        return state.economic_report

    # Best-effort: derive each closure record's region from its segment id prefix.
    def _seg_region(seg_id: str) -> str:
        if seg_id.startswith("NY-"):
            return "NY"
        if seg_id.startswith("NJ-"):
            return "NJ"
        return "CA"

    closures = [
        r for r in state.economic_report.get("highway_closures", [])
        if _seg_region(r.get("segment_id", "")) in keep
    ]
    return {**state.economic_report, "highway_closures": closures}


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


# ─── Demo flood triggers (Fix 6) ───────────────────────────────────────────

async def _auto_reset_demo_state(delay_seconds: float = 60.0):
    """Background task: revert demo_state to inactive after `delay_seconds`."""
    await asyncio.sleep(delay_seconds)
    state.demo_state.update({
        "active":      False,
        "scenario":    None,
        "started_at":  None,
        "description": "",
        "alerts":      [],
    })
    await refresh_all_data()


def _activate_flood_demo(scenario: str, region: str, segment: str, flood_prob: float,
                          description: str) -> dict:
    """Shared helper mirroring /demo/start's update pattern, plus Fix 6 fields."""
    trigger_time_utc = datetime.utcnow()
    state.demo_state.update({
        "active":           True,
        "scenario":         scenario,
        "started_at":       trigger_time_utc.isoformat(),
        "description":      description,
        "trigger_time_utc": trigger_time_utc.isoformat(),
        "region":           region,
        "flood_prob":       flood_prob,
        "segment":          segment,
        "edge_weight":      9.5,
    })
    asyncio.create_task(_auto_reset_demo_state(60.0))
    return {"trigger_time_utc": trigger_time_utc}


@app.post("/demo/flood", tags=["Demo"])
async def demo_flood_california():
    """Activate California flood demo scenario (US-101 Ventura→SLO)."""
    info = _activate_flood_demo(
        scenario="CA_101_FLOOD",
        region="california",
        segment="US-101 Ventura→SLO",
        flood_prob=0.78,
        description=(
            "Simulated flash flood on US-101 (Ventura→SLO), California. "
            "P(flood)=78% exceeds 0.65 pre-emptive threshold."
        ),
    )
    await refresh_all_data()
    trigger_time_utc = info["trigger_time_utc"]
    return {
        "status": "demo_active", "region": "california", "segment": "US-101 Ventura→SLO",
        "flood_prob": 0.78, "threshold": 0.65, "edge_weight": 9.5,
        "trigger_time_utc": trigger_time_utc.isoformat(),
        "trigger_time_display": format_incident_time(trigger_time_utc, "california"),
        "patent_note": "P(flood)=78% exceeds 0.65 threshold — pre-emptive trigger activated per patent Section 4.3.3",
        "reroute": {
            "corridor": "I-5 N", "reason": "P(flood)=78% exceeds 0.65 pre-emptive threshold",
            "eta_minutes": 26, "shelter": "Sacramento Convention Center", "hospital": "UC Davis Medical Center",
        },
        "reset_in_seconds": 60,
    }


@app.post("/demo/flood/njny", tags=["Demo"])
async def demo_flood_njny():
    """Activate NJ/NY flood demo scenario (US-1 near New Brunswick NJ)."""
    info = _activate_flood_demo(
        scenario="NJNY_RARITAN_FLOOD",
        region="njny",
        segment="US-1 near New Brunswick NJ",
        flood_prob=0.82,
        description=(
            "Simulated flash flood on US-1 near New Brunswick NJ. "
            "Raritan River gauge Bound Brook (USGS 01403060) rising. "
            "Historical context: Hurricane Ida 2021 Raritan flooding. "
            "P(flood)=82% exceeds 0.65 pre-emptive threshold."
        ),
    )
    await refresh_all_data()
    trigger_time_utc = info["trigger_time_utc"]
    return {
        "status": "demo_active", "region": "njny", "segment": "US-1 near New Brunswick NJ",
        "flood_prob": 0.82, "threshold": 0.65, "edge_weight": 9.5,
        "trigger_time_utc": trigger_time_utc.isoformat(),
        "trigger_time_display": format_incident_time(trigger_time_utc, "njny"),
        "patent_note": (
            "P(flood)=82% exceeds 0.65 threshold — pre-emptive trigger activated per patent Section 4.3.3. "
            "Raritan River gauge Bound Brook (USGS 01403060) rising. "
            "Historical context: Hurricane Ida 2021 Raritan flooding."
        ),
        "reroute": {
            "corridor": "I-287 W", "reason": "P(flood)=82% exceeds 0.65 pre-emptive threshold",
            "eta_minutes": 19, "shelter": "Rutgers Athletic Center", "hospital": "Robert Wood Johnson University Hospital",
        },
        "reset_in_seconds": 60,
    }


@app.post("/demo/flood/all", tags=["Demo"])
async def demo_flood_all():
    """Activate both California and NJ/NY flood demo scenarios simultaneously."""
    ca = await demo_flood_california()
    njny = await demo_flood_njny()
    return {"status": "demo_active", "region": "all", "california": ca, "njny": njny}


# ─── Demo zone overrides (Fix 9) ────────────────────────────────────────────

async def _auto_clear_zone_override(delay_seconds: float = 60.0):
    await asyncio.sleep(delay_seconds)
    state.zone_override = None
    await refresh_all_data()


@app.post("/demo/zone/{zone}", tags=["Demo"])
async def demo_zone_override(zone: str):
    """
    Force all segments to report as being in wildfire zone `zone` ("a"|"b"|"c")
    for demo purposes. Auto-clears after 60s or via POST /demo/zone/clear.
    """
    zone = zone.lower()
    if zone == "clear":
        state.zone_override = None
        return {"status": "zone_override_cleared"}
    if zone not in ("a", "b", "c"):
        raise HTTPException(400, "zone must be one of: a, b, c, clear")
    state.zone_override = zone
    asyncio.create_task(_auto_clear_zone_override(60.0))
    return {"status": "zone_override_active", "zone": zone, "reset_in_seconds": 60}


# Note: POST /demo/zone/clear is handled by the /demo/zone/{zone} route above
# (zone == "clear" branch) since FastAPI matches path params after literal
# routes are checked in declaration order — this route is declared first and
# already covers "clear", so no separate handler is needed.


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
            "live_pre_emptive_trigger": state.live_trigger,
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
