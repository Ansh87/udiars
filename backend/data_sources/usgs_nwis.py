"""
USGS NWIS — Stream Gauge Data Client
Fetches stage (ft) and computes stage rise rate (ft/hr) for California gauges.
Falls back to realistic synthetic data if the API is unavailable.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Representative California USGS stream gauges (site_no, name, lat, lon)
CA_GAUGES = [
    {"site_no": "11143000", "name": "Salinas R nr Bradley", "lat": 35.8583, "lon": -120.8022},
    {"site_no": "11169025", "name": "Coyote Ck at Madrone", "lat": 37.2533, "lon": -121.7397},
    {"site_no": "11176000", "name": "Guadalupe R at Hwy 101 SJ", "lat": 37.3455, "lon": -121.9089},
    {"site_no": "11181040", "name": "San Francisquito Ck at Stanford", "lat": 37.4272, "lon": -122.1553},
    {"site_no": "11042000", "name": "Santa Ana R nr Mentone", "lat": 34.0642, "lon": -117.1511},
    {"site_no": "11073495", "name": "Los Angeles R at Wardlow Rd", "lat": 33.8003, "lon": -118.1856},
    {"site_no": "11109000", "name": "Kern R nr Bakersfield", "lat": 35.3994, "lon": -118.9625},
    {"site_no": "11274500", "name": "San Joaquin R nr Fresno", "lat": 36.7302, "lon": -119.7880},
    {"site_no": "11377100", "name": "Sacramento R at Verona", "lat": 38.7896, "lon": -121.5997},
    {"site_no": "11458000", "name": "Russian R nr Guerneville", "lat": 38.5027, "lon": -123.0047},
]


class DataSourceStatus:
    def __init__(self):
        self.available = True
        self.last_check = None
        self.error_msg = ""


class USGSNWISClient:
    BASE_URL = "https://waterservices.usgs.gov/nwis/iv/"

    def __init__(self):
        self.status = DataSourceStatus()
        self._prev_stages: dict[str, float] = {}
        self._prev_time: Optional[datetime] = None

    async def fetch(self) -> list[dict]:
        """Return list of gauge readings with stage_ft and stage_rate_ft_hr."""
        try:
            data = await self._fetch_live()
            self.status.available = True
            self.status.error_msg = ""
            self.status.last_check = datetime.utcnow()
            return data
        except Exception as exc:
            self.status.available = False
            self.status.error_msg = str(exc)
            self.status.last_check = datetime.utcnow()
            logger.warning("USGS NWIS unavailable — using synthetic data: %s", exc)
            return self._synthetic_data()

    async def _fetch_live(self) -> list[dict]:
        site_ids = ",".join(g["site_no"] for g in CA_GAUGES)
        params = {
            "format": "json",
            "sites": site_ids,
            "parameterCd": "00065",   # gage height in feet
            "siteStatus": "active",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(self.BASE_URL, params=params)
            r.raise_for_status()
            raw = r.json()

        now = datetime.utcnow()
        results = []
        ts_series = raw.get("value", {}).get("timeSeries", [])

        for ts in ts_series:
            site_code = ts["sourceInfo"]["siteCode"][0]["value"]
            gauge_meta = next((g for g in CA_GAUGES if g["site_no"] == site_code), None)
            if not gauge_meta:
                continue

            values = ts.get("values", [{}])[0].get("value", [])
            if not values:
                continue

            try:
                stage_ft = float(values[-1]["value"])
            except (ValueError, KeyError):
                continue

            # Compute rise rate vs. previous reading
            prev_stage = self._prev_stages.get(site_code)
            if prev_stage is not None and self._prev_time is not None:
                hrs = (now - self._prev_time).total_seconds() / 3600
                rate = (stage_ft - prev_stage) / hrs if hrs > 0 else 0.0
            else:
                rate = 0.0

            self._prev_stages[site_code] = stage_ft
            results.append({
                "site_no": site_code,
                "name": gauge_meta["name"],
                "lat": gauge_meta["lat"],
                "lon": gauge_meta["lon"],
                "stage_ft": round(stage_ft, 2),
                "stage_rate_ft_hr": round(rate, 3),
                "timestamp": now.isoformat(),
                "source": "live",
            })

        self._prev_time = now
        return results

    def _synthetic_data(self) -> list[dict]:
        """Realistic synthetic gauge readings for California."""
        now = datetime.utcnow()
        results = []
        for gauge in CA_GAUGES:
            # Random but realistic stage values; occasional high-stage spikes
            stage_ft = round(random.uniform(1.5, 8.0), 2)
            rate = round(random.uniform(-0.1, 0.4), 3)  # slight rising trend
            results.append({
                "site_no": gauge["site_no"],
                "name": gauge["name"],
                "lat": gauge["lat"],
                "lon": gauge["lon"],
                "stage_ft": stage_ft,
                "stage_rate_ft_hr": rate,
                "timestamp": now.isoformat(),
                "source": "synthetic",
            })
        return results
