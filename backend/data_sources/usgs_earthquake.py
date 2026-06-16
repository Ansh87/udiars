"""
USGS Earthquake Hazards Program — Recent Seismic Events
Fetches M2.5+ earthquakes in/around California from the FDSN event API.
Falls back to synthetic events if API is unavailable.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Known active fault zones in California (for synthetic fallback)
CA_FAULT_ZONES = [
    {"name": "San Andreas Fault (S)",  "lat": 34.00, "lon": -117.50, "max_mag": 7.9},
    {"name": "San Andreas Fault (N)",  "lat": 37.80, "lon": -122.20, "max_mag": 7.9},
    {"name": "Hayward Fault",          "lat": 37.65, "lon": -122.10, "max_mag": 7.1},
    {"name": "Calaveras Fault",        "lat": 37.40, "lon": -121.80, "max_mag": 6.8},
    {"name": "Elsinore Fault",         "lat": 33.60, "lon": -117.25, "max_mag": 6.9},
    {"name": "San Jacinto Fault",      "lat": 33.80, "lon": -116.80, "max_mag": 7.2},
    {"name": "Garlock Fault",          "lat": 35.30, "lon": -118.30, "max_mag": 7.7},
    {"name": "Cascadia Subduction",    "lat": 41.00, "lon": -123.90, "max_mag": 9.0},
    {"name": "Imperial Fault",         "lat": 32.85, "lon": -115.50, "max_mag": 6.7},
    {"name": "Rodgers Creek Fault",    "lat": 38.30, "lon": -122.60, "max_mag": 7.0},
]


class USGSEarthquakeClient:
    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    def __init__(self):
        self.available = True
        self.last_check: Optional[datetime] = None
        self.error_msg = ""

    async def fetch(self, min_magnitude: float = 2.5, days_back: int = 7) -> list[dict]:
        try:
            data = await self._fetch_live(min_magnitude, days_back)
            self.available = True
            self.error_msg = ""
            self.last_check = datetime.utcnow()
            return data
        except Exception as exc:
            self.available = False
            self.error_msg = str(exc)
            self.last_check = datetime.utcnow()
            logger.warning("USGS Earthquake API unavailable — using synthetic data: %s", exc)
            return self._synthetic_data(min_magnitude)

    async def _fetch_live(self, min_mag: float, days_back: int) -> list[dict]:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)
        params = {
            "format": "geojson",
            "starttime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmagnitude": min_mag,
            "minlatitude": 32.5,
            "maxlatitude": 42.1,
            "minlongitude": -124.5,
            "maxlongitude": -114.1,
            "orderby": "time",
            "limit": 200,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(self.BASE_URL, params=params)
            r.raise_for_status()
            raw = r.json()

        results = []
        for feature in raw.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
            if not coords or coords[0] is None:
                continue

            mag = props.get("mag", 0)
            depth_km = coords[2] if len(coords) > 2 else 10.0
            pga = self._estimate_pga(mag, depth_km)

            results.append({
                "id": feature.get("id", ""),
                "place": props.get("place", "California"),
                "lat": round(coords[1], 4),
                "lon": round(coords[0], 4),
                "depth_km": round(depth_km or 10.0, 1),
                "magnitude": round(mag, 1),
                "time": props.get("time", 0),
                "pga_g": round(pga, 4),
                "mmi": props.get("mmi"),
                "source": "live",
            })
        return results

    def _synthetic_data(self, min_mag: float = 2.5, n: int = 8) -> list[dict]:
        now = datetime.utcnow()
        results = []
        for _ in range(n):
            fault = random.choice(CA_FAULT_ZONES)
            mag = round(random.uniform(min_mag, min(fault["max_mag"], 5.5)), 1)
            depth = round(random.uniform(3.0, 25.0), 1)
            lat = round(fault["lat"] + random.uniform(-0.5, 0.5), 4)
            lon = round(fault["lon"] + random.uniform(-0.5, 0.5), 4)
            pga = self._estimate_pga(mag, depth)
            results.append({
                "id": f"synth_{random.randint(100000,999999)}",
                "place": fault["name"],
                "lat": lat,
                "lon": lon,
                "depth_km": depth,
                "magnitude": mag,
                "time": int(now.timestamp() * 1000),
                "pga_g": round(pga, 4),
                "mmi": None,
                "source": "synthetic",
            })
        return results

    @staticmethod
    def _estimate_pga(magnitude: float, depth_km: float) -> float:
        """
        Simplified Atkinson-Boore (2003) PGA estimate at epicenter (g).
        For illustration — not for engineering use.
        """
        if magnitude <= 0:
            return 0.0
        r_hypo = max(depth_km, 1.0)
        log_pga = -1.715 + 0.500 * magnitude - 1.785 * (
            (r_hypo ** 2 + 7.35 ** 2) ** 0.5 / 10
        ) * 0.1 + 0.615
        pga = 10 ** log_pga / 980.665  # cm/s² → g
        return max(0.0, min(pga, 2.0))
