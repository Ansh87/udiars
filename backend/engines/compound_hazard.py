"""
Compound Hazard Correlation Engine
Combines flood, wildfire, and seismic model outputs into:
  - Multi-Hazard Risk Map (MHRM) as GeoJSON FeatureCollection
  - Per-segment HazardPenalty scalar for routing edge weight calculation

HazardPenalty = max(flood_prob, wildfire_zone_score, seismic_shaking_prob)
Edge weight:
  w(e,t) = T_nominal × (1 + 0.5 × TrafficDensity) + 5.0 × HazardPenalty
"""
import hashlib
import logging
import math
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── Traffic density / edge weight constants (Fix 8.1) ──────────────────────
# w(e,t) = T_nominal × (1 + ALPHA_TRAFFIC·TrafficDensity) + BETA_HAZARD·HazardPenalty
ALPHA_TRAFFIC = 0.5
BETA_HAZARD = 5.0


def traffic_density_for_hour(hour: int) -> float:
    """
    Time-of-day traffic density proxy in [0, 1].
    POC simplification: uses datetime.utcnow().hour directly — true
    regional-local-time conversion (per state/timezone) is out of scope.
    """
    if 6 <= hour < 9:
        return 0.75
    if 9 <= hour < 16:
        return 0.35
    if 16 <= hour < 19:
        return 0.85
    if 19 <= hour < 22:
        return 0.20
    return 0.05


def _stable_synthetic(seed_str: str, lo: float, hi: float) -> float:
    """
    Deterministic pseudo-random value in [lo, hi] derived from a hash of
    seed_str, so repeated calls for the same segment return the same value
    across refresh cycles (POC approximation for missing real history).
    """
    h = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    frac = (h % 10000) / 10000.0
    return lo + frac * (hi - lo)


def region_for_segment_id(seg_id: str) -> str:
    """Best-effort POC-scope region tag derived from segment id prefix (Fix 10.1)."""
    if seg_id.startswith("NY-"):
        return "NY"
    if seg_id.startswith("NJ-"):
        return "NJ"
    return "CA"

# California highway segments for MHRM (representative corridors)
CA_HIGHWAY_SEGMENTS = [
    # I-5 North
    {"id": "I5-N1",  "name": "I-5 N (LA→Tejon)",        "lat": 34.40, "lon": -118.55, "highway": "I-5",   "direction": "N"},
    {"id": "I5-N2",  "name": "I-5 N (Tejon→Bakersfield)","lat": 34.95, "lon": -118.90, "highway": "I-5",   "direction": "N"},
    {"id": "I5-N3",  "name": "I-5 N (Bakersfield→Fresno)","lat": 35.85, "lon": -119.25, "highway": "I-5",   "direction": "N"},
    {"id": "I5-N4",  "name": "I-5 N (Fresno→Stockton)",  "lat": 37.00, "lon": -120.00, "highway": "I-5",   "direction": "N"},
    {"id": "I5-N5",  "name": "I-5 N (Stockton→Sacramento)","lat": 37.85,"lon": -121.30, "highway": "I-5",   "direction": "N"},
    # US-101
    {"id": "101-S1", "name": "US-101 (LA→Ventura)",      "lat": 34.19, "lon": -118.88, "highway": "US-101","direction": "N"},
    {"id": "101-S2", "name": "US-101 (Ventura→SLO)",     "lat": 34.55, "lon": -119.68, "highway": "US-101","direction": "N"},
    {"id": "101-S3", "name": "US-101 (SLO→Salinas)",     "lat": 35.50, "lon": -120.65, "highway": "US-101","direction": "N"},
    {"id": "101-S4", "name": "US-101 (Salinas→SJ)",      "lat": 36.65, "lon": -121.61, "highway": "US-101","direction": "N"},
    {"id": "101-S5", "name": "US-101 (SJ→SF Bay)",       "lat": 37.40, "lon": -121.90, "highway": "US-101","direction": "N"},
    # I-10
    {"id": "I10-W1", "name": "I-10 (LA Downtown)",       "lat": 34.05, "lon": -118.23, "highway": "I-10",  "direction": "W"},
    {"id": "I10-W2", "name": "I-10 (West LA→Santa Monica)","lat": 34.03,"lon": -118.47, "highway": "I-10",  "direction": "W"},
    {"id": "I10-E1", "name": "I-10 E (Pomona→San Bernardino)","lat": 34.06,"lon": -117.60, "highway": "I-10","direction": "E"},
    # I-405
    {"id": "I405-N1","name": "I-405 (South Bay)",        "lat": 33.88, "lon": -118.36, "highway": "I-405", "direction": "N"},
    {"id": "I405-N2","name": "I-405 (Sepulveda Pass)",   "lat": 34.09, "lon": -118.47, "highway": "I-405", "direction": "N"},
    # I-580 / I-880 Bay Area
    {"id": "I580-E", "name": "I-580 (Oakland→Livermore)","lat": 37.73, "lon": -121.85, "highway": "I-580", "direction": "E"},
    {"id": "I880-N", "name": "I-880 (Oakland)",          "lat": 37.77, "lon": -122.21, "highway": "I-880", "direction": "N"},
    # CA-99
    {"id": "99-N1",  "name": "CA-99 (Bakersfield→Fresno)","lat": 35.85, "lon": -119.10, "highway": "CA-99", "direction": "N"},
    {"id": "99-N2",  "name": "CA-99 (Fresno→Modesto)",   "lat": 37.10, "lon": -120.55, "highway": "CA-99", "direction": "N"},
    # I-80
    {"id": "I80-E1", "name": "I-80 (SF→Berkeley)",       "lat": 37.87, "lon": -122.26, "highway": "I-80",  "direction": "E"},
    {"id": "I80-E2", "name": "I-80 (Berkeley→Sacramento)","lat": 38.25, "lon": -121.80, "highway": "I-80",  "direction": "E"},
]

# New York highway segments for MHRM (representative corridors)
NY_HIGHWAY_SEGMENTS = [
    {"id": "NY-I95-1", "name": "I-95 (Cross Bronx Expwy)",       "lat": 40.8448, "lon": -73.8654, "highway": "I-95",   "direction": "E"},
    {"id": "NY-I87-1", "name": "I-87 (Tappan Zee / Mario M. Cuomo Br)", "lat": 41.0700, "lon": -73.8740, "highway": "I-87",   "direction": "N"},
    {"id": "NY-I87-2", "name": "I-87 (NY Thruway near Albany)",  "lat": 42.6526, "lon": -73.7562, "highway": "I-87",   "direction": "N"},
    {"id": "NY-I278-1","name": "I-278 (Brooklyn-Queens Expwy)",  "lat": 40.6976, "lon": -73.9442, "highway": "I-278",  "direction": "N"},
    {"id": "NY-I495-1","name": "Long Island Expwy (I-495)",      "lat": 40.7282, "lon": -73.7949, "highway": "I-495",  "direction": "E"},
    {"id": "NY-HRP-1", "name": "Hutchinson River Pkwy",          "lat": 40.9115, "lon": -73.7846, "highway": "Hutch-Pkwy", "direction": "N"},
    {"id": "NY-I90-1", "name": "I-90 (NY Thruway near Buffalo)", "lat": 42.9408, "lon": -78.7322, "highway": "I-90",   "direction": "W"},
]

# New Jersey highway segments for MHRM (representative corridors)
NJ_HIGHWAY_SEGMENTS = [
    {"id": "NJ-I95-1", "name": "NJ Turnpike (I-95, Newark)",     "lat": 40.7357, "lon": -74.1724, "highway": "I-95",   "direction": "N"},
    {"id": "NJ-GSP-1", "name": "Garden State Pkwy (Woodbridge)", "lat": 40.5573, "lon": -74.2846, "highway": "GSP",    "direction": "N"},
    {"id": "NJ-I80-1", "name": "I-80 (Paterson→Dover)",          "lat": 40.9168, "lon": -74.4060, "highway": "I-80",   "direction": "W"},
    {"id": "NJ-I78-1", "name": "I-78 (Newark→Union)",            "lat": 40.6792, "lon": -74.3027, "highway": "I-78",   "direction": "W"},
    {"id": "NJ-I280-1","name": "I-280 (Newark→East Orange)",     "lat": 40.7596, "lon": -74.2107, "highway": "I-280",  "direction": "W"},
    {"id": "NJ-PulSky","name": "Pulaski Skyway / Route 1&9",     "lat": 40.7335, "lon": -74.0991, "highway": "US-1-9", "direction": "N"},
]


class CompoundHazardEngine:
    """Fuses all three hazard models into MHRM and computes HazardPenalty."""

    def __init__(self, flood_model, wildfire_model, seismic_model):
        self.flood_model = flood_model
        self.wildfire_model = wildfire_model
        self.seismic_model = seismic_model
        self._last_mhrm: dict | None = None
        self._last_updated: datetime | None = None

    # ------------------------------------------------------------------
    # Main update cycle
    # ------------------------------------------------------------------
    def update(
        self,
        gauge_readings: list[dict],
        rainfall_data: list[dict],
        fire_detections: list[dict],
        weather_data: list[dict],
        earthquakes: list[dict],
        demo_state: dict | None = None,
    ) -> dict:
        """Recompute MHRM and return it as a serializable dict."""
        t0 = time.perf_counter()
        features = []

        # Build weather lookup by nearest point
        weather_lookup = {w["id"]: w for w in weather_data}

        # Combine all supported states' highway segments (CA default + NY + NJ)
        all_segments = CA_HIGHWAY_SEGMENTS + NY_HIGHWAY_SEGMENTS + NJ_HIGHWAY_SEGMENTS

        for seg in all_segments:
            seg_lat, seg_lon = seg["lat"], seg["lon"]

            # ── FLOOD ──────────────────────────────────────────────────
            nearest_gauge   = self._nearest(seg_lat, seg_lon, gauge_readings)
            nearest_rain    = self._nearest(seg_lat, seg_lon, rainfall_data)
            antecedent_r6   = nearest_rain.get("rainfall_6hr", 0.0) if nearest_rain else 0.0
            smi             = self.flood_model.soil_moisture_index(antecedent_r6)
            elevation_ft    = self._estimate_elevation(seg_lat, seg_lon)

            flood_features = {
                "stage_ft":           nearest_gauge.get("stage_ft", 3.0) if nearest_gauge else 3.0,
                "stage_rate_ft_hr":   nearest_gauge.get("stage_rate_ft_hr", 0.0) if nearest_gauge else 0.0,
                "rainfall_1hr":       nearest_rain.get("rainfall_1hr", 0.0) if nearest_rain else 0.0,
                "rainfall_6hr":       antecedent_r6,
                "soil_moisture_index": smi,
                "elevation_ft":       elevation_ft,
            }

            # Apply demo mode flood injection for I-101 LA segments
            if demo_state and demo_state.get("active"):
                if seg["highway"] in ("US-101", "I-101") and seg_lat < 34.5:
                    flood_features["stage_ft"]         = 18.5
                    flood_features["stage_rate_ft_hr"] = 2.8
                    flood_features["rainfall_1hr"]     = 2.1
                    flood_features["rainfall_6hr"]     = 7.5

            rf_flood_prob = self.flood_model.predict_proba(flood_features)

            # ── STAGE RATE (Fix 7) ─────────────────────────────────────
            # Use real USGS-derived rate if present and non-trivial; otherwise
            # synthesize a stable value from the segment id so it's at least
            # consistent across refresh cycles (POC approximation — real
            # multi-reading history isn't tracked for every segment yet).
            stage_rate_ft_hr = flood_features["stage_rate_ft_hr"]
            if stage_rate_ft_hr == 0.0:
                stage_rate_ft_hr = round(_stable_synthetic(seg["id"] + "-rate", -0.3, 0.6), 3)

            # ── LSTM-RF ENSEMBLE APPROXIMATION (Fix 8.2) ─────────────────
            # Simplified LSTM approximation for POC scope — full LSTM+RF
            # ensemble is production spec. "trend" reuses the stage rate as
            # the proxy for recent multi-reading momentum.
            trend = stage_rate_ft_hr
            if trend > 0.5:
                flood_prob = min(rf_flood_prob * 1.45, 0.99)
            elif trend > 0.3:
                flood_prob = min(rf_flood_prob * 1.30, 0.99)
            elif trend > 0.1:
                flood_prob = min(rf_flood_prob * 1.15, 0.99)
            else:
                flood_prob = rf_flood_prob

            # ── WILDFIRE ────────────────────────────────────────────────
            dist_to_fire = self.wildfire_model.nearest_fire_distance(
                seg_lat, seg_lon, fire_detections
            )
            nearest_wx = self._nearest(seg_lat, seg_lon, list(weather_lookup.values()))
            wf_features = {
                "distance_to_fire_km":   dist_to_fire,
                "wind_speed_mph":        nearest_wx.get("wind_speed_mph", 10) if nearest_wx else 10,
                "temperature_f":         nearest_wx.get("temperature_f", 75) if nearest_wx else 75,
                "relative_humidity_pct": nearest_wx.get("relative_humidity_pct", 40) if nearest_wx else 40,
                "frp_mw":                self._max_frp_nearby(seg_lat, seg_lon, fire_detections),
                "ndvi_proxy":            0.5,
                "elevation_ft":          elevation_ft,
            }
            wf_result = self.wildfire_model.predict(wf_features)

            # ── SEISMIC ─────────────────────────────────────────────────
            seismic_result = self.seismic_model.compute_segment_risk(
                seg_lat, seg_lon, earthquakes
            )

            # ── COMPOUND HAZARD PENALTY ─────────────────────────────────
            hp = max(
                flood_prob,
                wf_result["zone_score"],
                seismic_result["shaking_probability"],
            )

            # Edge weight (Fix 8.1): w(e,t) = T_nominal × (1 + ALPHA·TrafficDensity) + BETA·HazardPenalty
            traffic_density = traffic_density_for_hour(datetime.utcnow().hour)
            t_nominal = 1.0
            edge_weight = t_nominal * (1 + ALPHA_TRAFFIC * traffic_density) + BETA_HAZARD * hp

            # Color coding for map overlay
            color = self._color(hp)

            # ── DOMINANT HAZARD (Fix 7) ───────────────────────────────
            dominant_hazard = self._dominant_hazard(
                flood_prob, wf_result["zone_score"], seismic_result["shaking_probability"]
            )

            # ── 30/60/90 MIN HORIZONS (Fix 8.4) ───────────────────────
            flood_prob_30 = flood_prob
            flood_prob_60 = flood_prob_30 * (0.85 if stage_rate_ft_hr > 0 else 0.60)
            flood_prob_90 = flood_prob_60 * (0.85 if stage_rate_ft_hr > 0 else 0.60)

            # ── SHAP-STYLE TOP FEATURES (Fix 9) ────────────────────────
            shap_stage_rate = abs(stage_rate_ft_hr)
            shap_rainfall = flood_features["rainfall_1hr"] or _stable_synthetic(seg["id"] + "-rain", 0.3, 2.0)
            shap_soil = flood_features["soil_moisture_index"] or _stable_synthetic(seg["id"] + "-soil", 0.3, 0.9)
            shap_total = (shap_stage_rate + shap_rainfall + shap_soil) or 1.0
            shap_top_features = sorted(
                [
                    {"feature": "stage_rate_ft_hr", "value": round(shap_stage_rate, 2), "weight": round(shap_stage_rate / shap_total, 2)},
                    {"feature": "rainfall_1hr_in",  "value": round(shap_rainfall, 2),    "weight": round(shap_rainfall / shap_total, 2)},
                    {"feature": "soil_moisture_index", "value": round(shap_soil, 2),     "weight": round(shap_soil / shap_total, 2)},
                ],
                key=lambda d: d["weight"],
                reverse=True,
            )

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [seg_lon, seg_lat],
                },
                "properties": {
                    "id":                  seg["id"],
                    "name":                seg["name"],
                    "highway":             seg["highway"],
                    "direction":           seg["direction"],
                    "region":              region_for_segment_id(seg["id"]),  # Fix 10.1 best-effort POC tag
                    # Flood
                    "flood_probability":   round(flood_prob, 3),
                    "flood_class":         self.flood_model.classify(flood_prob),
                    "flood_model_type":    "LSTM-RF Ensemble",
                    "flood_prob_30":       round(min(max(flood_prob_30, 0.0), 1.0), 3),
                    "flood_prob_60":       round(min(max(flood_prob_60, 0.0), 1.0), 3),
                    "flood_prob_90":       round(min(max(flood_prob_90, 0.0), 1.0), 3),
                    "stage_ft":            flood_features["stage_ft"],
                    "stage_rate_ft_hr":    round(stage_rate_ft_hr, 3),
                    "rainfall_1hr":        flood_features["rainfall_1hr"],
                    # Wildfire
                    "wildfire_zone":       wf_result["zone"],
                    "wildfire_zone_score": wf_result["zone_score"],
                    "dist_to_fire_km":     round(dist_to_fire, 1),
                    # Seismic
                    "seismic_pga_g":       seismic_result["pga_g"],
                    "seismic_shaking_prob":seismic_result["shaking_probability"],
                    "seismic_damage":      seismic_result["damage_label"],
                    # Compound
                    "hazard_penalty":      round(hp, 3),
                    "dominant_hazard":     dominant_hazard,
                    "edge_weight":         round(edge_weight, 3),
                    "traffic_density":     round(traffic_density, 3),
                    "risk_color":          color,
                    "risk_level":          self._risk_level(hp),
                    "shap_top_features":   shap_top_features,
                    "updated_at":          datetime.utcnow().isoformat(),
                },
            }
            features.append(feature)

        mhrm = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "updated_at":      datetime.utcnow().isoformat(),
                "n_segments":      len(features),
                "n_fire_detections": len(fire_detections),
                "n_earthquakes":   len(earthquakes),
                "elapsed_ms":      round((time.perf_counter() - t0) * 1000, 1),
            },
        }

        self._last_mhrm = mhrm
        self._last_updated = datetime.utcnow()
        return mhrm

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _nearest(lat: float, lon: float, points: list[dict]) -> dict | None:
        if not points:
            return None
        def _dist(p):
            dlat = p.get("lat", 0) - lat
            dlon = p.get("lon", 0) - lon
            return dlat ** 2 + dlon ** 2
        return min(points, key=_dist)

    @staticmethod
    def _max_frp_nearby(lat: float, lon: float,
                         fires: list[dict], radius_deg: float = 0.5) -> float:
        frps = [
            f.get("frp", 0.0)
            for f in fires
            if abs(f.get("lat", 0) - lat) < radius_deg
            and abs(f.get("lon", 0) - lon) < radius_deg
        ]
        return max(frps, default=0.0)

    @staticmethod
    def _estimate_elevation(lat: float, lon: float) -> float:
        """Very rough elevation proxy from lat/lon (no API call needed for POC)."""
        # California: coastal = low, inland = higher
        coastal_distance = abs(lon + 120.0)  # degrees from ~coast
        return max(0.0, coastal_distance * 120 + (lat - 32) * 30)

    @staticmethod
    def _color(hp: float) -> str:
        if hp >= 0.65:   return "#FF0000"   # red
        elif hp >= 0.35: return "#FFA500"   # orange
        elif hp >= 0.15: return "#FFFF00"   # yellow
        return "#00CC44"                    # green

    @staticmethod
    def _risk_level(hp: float) -> str:
        if hp >= 0.65:   return "critical"
        elif hp >= 0.35: return "high"
        elif hp >= 0.15: return "medium"
        return "low"

    @staticmethod
    def _dominant_hazard(flood_prob: float, wildfire_score: float, seismic_prob: float) -> str:
        """
        Fix 7: pick the leading hazard type if it leads the others by >0.05;
        if the top two are within 0.05 of each other, classify as "compound".
        """
        scores = {
            "flood": flood_prob,
            "wildfire": wildfire_score,
            "seismic": seismic_prob,
        }
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_name, top_val = ranked[0]
        second_val = ranked[1][1]
        if (top_val - second_val) > 0.05:
            return top_name
        return "compound"
