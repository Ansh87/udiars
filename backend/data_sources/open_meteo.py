"""
Open-Meteo — Wind Speed & Temperature for Wildfire Risk
Fetches current wind speed (mph) and temperature (°F) at key California locations.
Falls back to synthetic data if API is unavailable.
"""
import logging
import random
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CA_WEATHER_POINTS = [
    {"id": "la",    "name": "Los Angeles",         "lat": 34.05,  "lon": -118.25},
    {"id": "sf",    "name": "San Francisco",       "lat": 37.77,  "lon": -122.42},
    {"id": "sac",   "name": "Sacramento",          "lat": 38.58,  "lon": -121.49},
    {"id": "sd",    "name": "San Diego",           "lat": 32.72,  "lon": -117.15},
    {"id": "fres",  "name": "Fresno",              "lat": 36.74,  "lon": -119.79},
    {"id": "bak",   "name": "Bakersfield",         "lat": 35.37,  "lon": -119.02},
    {"id": "palm",  "name": "Palm Springs",        "lat": 33.83,  "lon": -116.54},
    {"id": "red",   "name": "Redding",             "lat": 40.58,  "lon": -122.39},
    {"id": "napa",  "name": "Napa",                "lat": 38.30,  "lon": -122.29},
    {"id": "sb",    "name": "Santa Barbara",       "lat": 34.42,  "lon": -119.70},
]


class OpenMeteoClient:
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
            logger.warning("Open-Meteo unavailable — using synthetic data: %s", exc)
            return self._synthetic_data()

    async def _fetch_live(self) -> list[dict]:
        results = []
        now = datetime.utcnow()
        async with httpx.AsyncClient(timeout=20) as client:
            for pt in CA_WEATHER_POINTS:
                params = {
                    "latitude": pt["lat"],
                    "longitude": pt["lon"],
                    "current_weather": True,
                    "hourly": "relativehumidity_2m,soil_moisture_0_1cm",
                    "forecast_days": 1,
                    "wind_speed_unit": "mph",
                    "temperature_unit": "fahrenheit",
                }
                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()
                raw = r.json()

                cw = raw.get("current_weather", {})
                hourly = raw.get("hourly", {})
                rh_vals = hourly.get("relativehumidity_2m", [50])
                sm_vals = hourly.get("soil_moisture_0_1cm", [0.2])

                results.append({
                    "id": pt["id"],
                    "name": pt["name"],
                    "lat": pt["lat"],
                    "lon": pt["lon"],
                    "wind_speed_mph": round(cw.get("windspeed", 0), 1),
                    "wind_direction_deg": round(cw.get("winddirection", 0), 0),
                    "temperature_f": round(cw.get("temperature", 65), 1),
                    "relative_humidity_pct": round(rh_vals[-1] if rh_vals else 50, 0),
                    "soil_moisture": round(sm_vals[-1] if sm_vals else 0.2, 3),
                    "timestamp": now.isoformat(),
                    "source": "live",
                })
        return results

    def _synthetic_data(self) -> list[dict]:
        now = datetime.utcnow()
        # Diablo / Santa Ana wind conditions have higher wind speeds
        results = []
        for pt in CA_WEATHER_POINTS:
            inland = pt["lon"] > -118.5
            wind = round(random.uniform(8, 35) if inland else random.uniform(3, 18), 1)
            temp = round(random.uniform(70, 105) if inland else random.uniform(55, 85), 1)
            rh = round(random.uniform(10, 30) if inland else random.uniform(35, 75), 0)
            results.append({
                "id": pt["id"],
                "name": pt["name"],
                "lat": pt["lat"],
                "lon": pt["lon"],
                "wind_speed_mph": wind,
                "wind_direction_deg": round(random.uniform(0, 360), 0),
                "temperature_f": temp,
                "relative_humidity_pct": rh,
                "soil_moisture": round(random.uniform(0.05, 0.35), 3),
                "timestamp": now.isoformat(),
                "source": "synthetic",
            })
        return results
