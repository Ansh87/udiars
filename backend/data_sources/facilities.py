"""
Emergency Facilities Reference Data
Shelters and hospitals used by the routing engine's fallback responses and
by the GET /facilities endpoint. California lists are POC placeholders
(reasonable real-world-ish locations); NY/NJ lists were added per the
patent demo requirements (Fix 11).

Shape: {"name": str, "lat": float, "lon": float, "capacity": int}            (shelters)
       {"name": str, "lat": float, "lon": float, "beds": int}                (hospitals)
"""

# ── California ────────────────────────────────────────────────────────────
CA_SHELTERS = [
    {"name": "Sacramento Convention Center", "lat": 38.5779, "lon": -121.5018, "capacity": 10000},
    {"name": "Fresno Convention Center",      "lat": 36.7378, "lon": -119.7871, "capacity": 8000},
    {"name": "San Luis Obispo Shelter",       "lat": 35.2828, "lon": -120.6596, "capacity": 3000},
    {"name": "Los Angeles Convention Center", "lat": 34.0403, "lon": -118.2696, "capacity": 15000},
]

CA_HOSPITALS = [
    {"name": "UC Davis Medical Center",            "lat": 38.5538, "lon": -121.4567, "beds": 627},
    {"name": "Community Regional Medical Center",  "lat": 36.7567, "lon": -119.7872, "beds": 685},
    {"name": "Sierra Vista Regional Medical",       "lat": 35.2719, "lon": -120.6498, "beds": 165},
    {"name": "Cedars-Sinai Medical Center",          "lat": 34.0759, "lon": -118.3800, "beds": 886},
]

# ── New Jersey ───────────────────────────────────────────────────────────
NJ_SHELTERS = [
    {"name": "Rutgers Athletic Center Piscataway", "lat": 40.5234, "lon": -74.4342, "capacity": 8000},
    {"name": "Meadowlands Expo Center Secaucus",   "lat": 40.7862, "lon": -74.0776, "capacity": 12000},
    {"name": "Boardwalk Hall Atlantic City",        "lat": 39.3612, "lon": -74.4265, "capacity": 14000},
    {"name": "Sun National Bank Ctr Trenton",       "lat": 40.2190, "lon": -74.7564, "capacity": 9000},
]

NJ_HOSPITALS = [
    {"name": "Robert Wood Johnson NB NJ", "lat": 40.4954, "lon": -74.4483, "beds": 614},
    {"name": "Newark Beth Israel",        "lat": 40.7244, "lon": -74.2099, "beds": 669},
    {"name": "Jersey City Medical Center","lat": 40.7178, "lon": -74.0776, "beds": 349},
    {"name": "Cooper University Hospital Camden", "lat": 39.9440, "lon": -75.1160, "beds": 635},
]

# ── New York ─────────────────────────────────────────────────────────────
NY_SHELTERS = [
    {"name": "Javits Center NYC",          "lat": 40.7573, "lon": -74.0021, "capacity": 20000},
    {"name": "Nassau Coliseum Uniondale",  "lat": 40.7227, "lon": -73.5900, "capacity": 15000},
    {"name": "Times Union Center Albany",  "lat": 42.6583, "lon": -73.7547, "capacity": 8000},
    {"name": "KeyBank Center Buffalo",     "lat": 42.8750, "lon": -78.8764, "capacity": 10000},
]

NY_HOSPITALS = [
    {"name": "NYU Langone Medical NYC",   "lat": 40.7424, "lon": -73.9736, "beds": 820},
    {"name": "Bellevue Hospital NYC",     "lat": 40.7394, "lon": -73.9756, "beds": 828},
    {"name": "NewYork-Presbyterian",      "lat": 40.8401, "lon": -73.9428, "beds": 2478},
    {"name": "Albany Medical Center",     "lat": 42.6548, "lon": -73.7768, "beds": 714},
    {"name": "Buffalo General Medical",   "lat": 42.8997, "lon": -78.8720, "beds": 496},
]


def get_facilities(region: str = "all") -> dict:
    """Return {"shelters": [...], "hospitals": [...]} filtered by region.

    region: "california" -> CA only, "njny"/"nj"/"ny" -> NJ+NY, anything
    else (including "all") -> everything.
    """
    region = (region or "all").lower()
    if region == "california" or region == "ca":
        return {"shelters": CA_SHELTERS, "hospitals": CA_HOSPITALS}
    if region in ("njny", "nj", "ny"):
        return {
            "shelters": NJ_SHELTERS + NY_SHELTERS,
            "hospitals": NJ_HOSPITALS + NY_HOSPITALS,
        }
    return {
        "shelters": CA_SHELTERS + NJ_SHELTERS + NY_SHELTERS,
        "hospitals": CA_HOSPITALS + NJ_HOSPITALS + NY_HOSPITALS,
    }
