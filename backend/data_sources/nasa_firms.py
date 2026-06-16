"""
NASA FIRMS — Fire Information for Resource Management System
Fetches active fire detections (VIIRS/MODIS) over California.
Requires a free MAP_KEY from https://firms.modaps.eosdis.nasa.gov/api/
Falls back to synthetic fire detections if key not set or API unavailable.
"""
import logging
import os
import random
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Bounding box for California
CA_BBOX = {"west": -124.48, "south": 32.53, "east": -114.13, "north": 42.01}

# Known high-fire-risk areas in California (for synthetic fallback)
CA_FIRE_ZONES = [
    {"name": "Angeles NF",        "lat": 34.25,  "lon": -117.88, "risk": "high"},
    {"name": "San Bernardino NF", "lat": 34.18,  "lon": -117.10, "risk": "high"},
    {"name": "Shasta-Trinity NF", "lat": 40.90,  "lon": -122.60, "risk": "high"},
    {"name": "Mendocino NF",      "lat": 39.30,  "lon": -122.85, "risk": "high"},
    {"name": "Plumas NF",         "lat": 40.00,  "lon": -120.70, "risk": "medium"},
    {"name": "Los Padres NF",     "lat": 34.65,  "lon": -119.80, "risk": "medium"},
    {"name": "Tahoe NF",          "lat": 39.25,  "lon": -120.48, "risk": "medium"},
    {"name": "Klamath NF",        "lat": 41.75,  "lon": -122.85, "risk": "medium"},
    {"name": "Cleveland NF",      "lat": 33.35,  "lon": -116.75, "risk": "low"},
    {"name": "Six Rivers NF",     "lat": 41.05,  "lon": -123.70, "risk": "low"},
]

# Known fire-risk areas in New York (upstate forests / Pine Barrens-adjacent)
NY_FIRE_ZONES = [
    {"name": "Adirondack Park",       "lat": 44.00, "lon": -74.30, "risk": "medium"},
    {"name": "Catskill Park",         "lat": 42.10, "lon": -74.40, "risk": "medium"},
    {"name": "Long Island Pine Barrens", "lat": 40.85, "lon": -72.75, "risk": "low"},
]

# Known fire-risk areas in New Jersey (Pine Barrens have real wildfire risk)
NJ_FIRE_ZONES = [
    {"name": "NJ Pine Barrens (Wharton SF)", "lat": 39.70, "lon": -74.55, "risk": "high"},
    {"name": "NJ Pine Barrens (Bass River SF)", "lat": 39.62, "lon": -74.43, "risk": "medium"},
    {"name": "Wawayanda SF (Highlands)", "lat": 41.18, "lon": -74.47, "risk": "low"},
]


class NASAFIRMSClient:
    BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

    def __init__(self):
        self.api_key = os.getenv("NASA_FIRMS_API_KEY", "")
        self.available = True
        self.last_check: Optional[datetime] = None
        self.error_msg = ""

    async def fetch(self) -> list[dict]:
        if not self.api_key:
            self.available = False
            self.error_msg = "NASA_FIRMS_API_KEY not set"
            self.last_check = datetime.utcnow()
            logger.info("NASA FIRMS key not configured — using synthetic fire data")
            return self._synthetic_data()
        try:
            data = await self._fetch_live()
            self.available = True
            self.error_msg = ""
            self.last_check = datetime.utcnow()
            return data
        except Exception as exc:
            self.available = False
            self.error_msg = str(exc)
            self.last_check = datetime.utcnow()
            logger.warning("NASA FIRMS unavailable — using synthetic data: %s", exc)
            return self._synthetic_data()

    async def _fetch_live(self) -> list[dict]:
        """Fetch VIIRS I-Band 375m detections for California, last 24 hours."""
        bbox_str = (
            f"{CA_BBOX['west']},{CA_BBOX['south']},"
            f"{CA_BBOX['east']},{CA_BBOX['north']}"
        )
        url = f"{self.BASE_URL}/{self.api_key}/VIIRS_SNPP_NRT/{bbox_str}/1"  # 1 day
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            text = r.text

        results = []
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return results

        headers = [h.strip() for h in lines[0].split(",")]
        now = datetime.utcnow()

        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < len(headers):
                continue
            row = dict(zip(headers, [p.strip() for p in parts]))
            try:
                results.append({
                    "lat": float(row.get("latitude", 0)),
                    "lon": float(row.get("longitude", 0)),
                    "brightness": float(row.get("bright_ti4", row.get("brightness", 300))),
                    "frp": float(row.get("frp", 0)),          # Fire Radiative Power MW
                    "confidence": row.get("confidence", "nominal"),
                    "acq_datetime": f"{row.get('acq_date','')} {row.get('acq_time','')}",
                    "instrument": "VIIRS",
                    "source": "live",
                    "fetched_at": now.isoformat(),
                })
            except (ValueError, KeyError):
                continue
        return results

    def _synthetic_data(self, n_detections: int = 15) -> list[dict]:
        """Generate plausible synthetic fire detections around known fire zones."""
        now = datetime.utcnow()
        results = []
        all_zones = CA_FIRE_ZONES + NY_FIRE_ZONES + NJ_FIRE_ZONES
        zones = [z for z in all_zones if z["risk"] in ("high", "medium")]
        for _ in range(n_detections):
            zone = random.choice(zones)
            lat_off = random.uniform(-0.3, 0.3)
            lon_off = random.uniform(-0.3, 0.3)
            results.append({
                "lat": round(zone["lat"] + lat_off, 4),
                "lon": round(zone["lon"] + lon_off, 4),
                "brightness": round(random.uniform(310, 420), 1),
                "frp": round(random.uniform(5, 80), 1),
                "confidence": random.choice(["low", "nominal", "high"]),
                "acq_datetime": now.strftime("%Y-%m-%d %H%M"),
                "instrument": "VIIRS_synthetic",
                "zone_name": zone["name"],
                "source": "synthetic",
                "fetched_at": now.isoformat(),
            })
        return results
