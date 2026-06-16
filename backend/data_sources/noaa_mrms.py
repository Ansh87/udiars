"""
NOAA MRMS — Multi-Radar/Multi-Sensor Rainfall Accumulation
Fetches 1-hr and 6-hr QPE (quantitative precipitation estimates) for California.
MRMS data is typically accessed via NCEP/GDS; this client calls the public GFS
endpoint as a proxy and falls back to synthetic data when unavailable.
"""
import logging
import random
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# California rainfall reference points (lat, lon, label)
CA_RAIN_POINTS = [
    {"id": "ca_la",     "name": "Los Angeles Basin",    "lat": 34.05,  "lon": -118.25},
    {"id": "ca_sf",     "name": "San Francisco Bay",    "lat": 37.75,  "lon": -122.45},
    {"id": "ca_sac",    "name": "Sacramento Valley",    "lat": 38.55,  "lon": -121.50},
    {"id": "ca_sd",     "name": "San Diego",            "lat": 32.72,  "lon": -117.15},
    {"id": "ca_fres",   "name": "Fresno / Central Val", "lat": 36.74,  "lon": -119.79},
    {"id": "ca_bak",    "name": "Bakersfield",          "lat": 35.37,  "lon": -119.02},
    {"id": "ca_sm",     "name": "Santa Maria",          "lat": 34.95,  "lon": -120.44},
    {"id": "ca_napa",   "name": "Napa Valley",          "lat": 38.30,  "lon": -122.29},
    {"id": "ca_red",    "name": "Redding",              "lat": 40.58,  "lon": -122.39},
    {"id": "ca_eur",    "name": "Eureka / NorCal",      "lat": 40.80,  "lon": -124.16},
]


class NOAAMRMSClient:
    # Open-Meteo provides real-time precipitation; use as MRMS proxy
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self):
        self.available = True
        self.last_check: Optional[datetime] = None
        self.error_msg = ""

    async def fetch(self) -> list[dict]:
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
            logger.warning("NOAA MRMS (proxy) unavailable — using synthetic data: %s", exc)
            return self._synthetic_data()

    async def _fetch_live(self) -> list[dict]:
        results = []
        now = datetime.utcnow()

        # Batch calls: fetch precipitation for all points
        async with httpx.AsyncClient(timeout=20) as client:
            for pt in CA_RAIN_POINTS:
                params = {
                    "latitude": pt["lat"],
                    "longitude": pt["lon"],
                    "hourly": "precipitation",
                    "forecast_days": 1,
                    "timezone": "America/Los_Angeles",
                }
                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()
                raw = r.json()

                hourly = raw.get("hourly", {})
                precip_vals = hourly.get("precipitation", [])

                # Last available hour
                r1hr = precip_vals[-1] if precip_vals else 0.0
                r6hr = sum(precip_vals[-6:]) if len(precip_vals) >= 6 else sum(precip_vals)
                # Convert mm → inches
                r1hr_in = round((r1hr or 0) * 0.0394, 3)
                r6hr_in = round((r6hr or 0) * 0.0394, 3)

                results.append({
                    "id": pt["id"],
                    "name": pt["name"],
                    "lat": pt["lat"],
                    "lon": pt["lon"],
                    "rainfall_1hr": r1hr_in,
                    "rainfall_6hr": r6hr_in,
                    "timestamp": now.isoformat(),
                    "source": "live",
                })
        return results

    def _synthetic_data(self) -> list[dict]:
        now = datetime.utcnow()
        results = []
        for pt in CA_RAIN_POINTS:
            r1 = round(random.uniform(0.0, 0.8), 3)
            r6 = round(r1 * random.uniform(3.5, 6.5), 3)
            results.append({
                "id": pt["id"],
                "name": pt["name"],
                "lat": pt["lat"],
                "lon": pt["lon"],
                "rainfall_1hr": r1,
                "rainfall_6hr": r6,
                "timestamp": now.isoformat(),
                "source": "synthetic",
            })
        return results
