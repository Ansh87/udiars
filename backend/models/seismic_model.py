"""
Seismic Damage / Ground Shaking Model
Combines USGS earthquake data with NSHM-2023-style PGA estimates to compute
infrastructure damage probability per road segment / bridge.

HAZUS-MH simplified fragility categories (damage states):
  0 = None, 1 = Slight, 2 = Moderate, 3 = Extensive, 4 = Complete

PGA-based fragility (lognormal CDF) for Highway Bridge Type HWB1 (K-frame).
Median PGA values from HAZUS-MH 2.1 Table 7.3:
  Slight: 0.10g, Moderate: 0.20g, Extensive: 0.50g, Complete: 0.80g
Beta (dispersion): 0.60
"""
import logging
import math
import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)

DAMAGE_STATES  = {0: "None", 1: "Slight", 2: "Moderate", 3: "Extensive", 4: "Complete"}
BRIDGE_TYPES   = ["HWB1", "HWB2", "HWB3", "HWB4"]

# Fragility parameters [median_pga_g, beta] per damage state (HAZUS-MH HWB1)
FRAGILITY = {
    1: (0.10, 0.60),  # Slight
    2: (0.20, 0.60),  # Moderate
    3: (0.50, 0.60),  # Extensive
    4: (0.80, 0.60),  # Complete
}

# Replacement cost proxies (USD millions) per bridge type
REPLACEMENT_COST_M = {"HWB1": 8.5, "HWB2": 12.0, "HWB3": 6.0, "HWB4": 20.0}
DAMAGE_STATE_FACTOR = {0: 0.0, 1: 0.03, 2: 0.08, 3: 0.25, 4: 1.0}


class SeismicModel:
    """PGA-based bridge fragility and ground shaking probability model."""

    def __init__(self):
        # Synthetic bridge inventory (NBI subset for CA + NY + NJ POC)
        self.bridges = (
            self._synthetic_bridge_inventory()
            + self._ny_bridge_inventory()
            + self._nj_bridge_inventory()
        )
        self._trained = True  # no ML training needed — physics-based

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compute_segment_risk(self, lat: float, lon: float,
                              earthquakes: list[dict]) -> dict:
        """
        Compute seismic risk metrics for a road segment / location.
        Returns pga_g, shaking_probability, damage_state, damage_label.
        """
        pga = self._aggregate_pga(lat, lon, earthquakes)
        damage_state, damage_proba = self._fragility_damage_state(pga)
        shaking_prob = self._shaking_probability(pga)

        return {
            "pga_g": round(pga, 4),
            "shaking_probability": round(shaking_prob, 3),
            "damage_state": damage_state,
            "damage_label": DAMAGE_STATES[damage_state],
            "damage_probability": round(damage_proba, 3),
        }

    def affected_bridges(self, earthquakes: list[dict],
                          radius_km: float = 50.0) -> list[dict]:
        """Return bridges within radius_km of any significant earthquake."""
        if not earthquakes:
            return []

        results = []
        for bridge in self.bridges:
            min_dist = min(
                self._haversine_km(bridge["lat"], bridge["lon"], eq["lat"], eq["lon"])
                for eq in earthquakes
            )
            if min_dist > radius_km:
                continue

            # Find the nearest significant earthquake for PGA calculation
            nearest = min(
                earthquakes,
                key=lambda eq: self._haversine_km(
                    bridge["lat"], bridge["lon"], eq["lat"], eq["lon"]
                )
            )

            pga = nearest.get("pga_g", 0.0)
            damage_state, damage_prob = self._fragility_damage_state(pga)
            replacement = REPLACEMENT_COST_M.get(bridge["type"], 8.5)
            economic_loss = replacement * DAMAGE_STATE_FACTOR[damage_state]

            results.append({
                **bridge,
                "nearest_eq_mag": nearest.get("magnitude", 0),
                "distance_to_eq_km": round(min_dist, 1),
                "pga_g": round(pga, 4),
                "damage_state": damage_state,
                "damage_label": DAMAGE_STATES[damage_state],
                "damage_probability": round(damage_prob, 3),
                "economic_loss_m": round(economic_loss, 2),
            })
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2) -> float:
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _aggregate_pga(lat: float, lon: float, earthquakes: list[dict]) -> float:
        """Sum PGA contributions using square-root-sum-of-squares (SRSS)."""
        if not earthquakes:
            return 0.0
        pgas = []
        for eq in earthquakes:
            dist_km = SeismicModel._haversine_km(lat, lon, eq["lat"], eq["lon"])
            # Attenuate PGA with distance (simplified r^-1.5 decay)
            base_pga = eq.get("pga_g", 0.0)
            if dist_km < 1:
                dist_km = 1.0
            attenuated = base_pga * (1.0 / (dist_km / 10.0) ** 1.5)
            pgas.append(attenuated)
        return min(float(np.sqrt(np.sum(np.square(pgas)))), 2.0)

    @staticmethod
    def _fragility_damage_state(pga_g: float) -> tuple[int, float]:
        """Return (damage_state, exceedance_probability) using lognormal CDF."""
        if pga_g <= 0:
            return 0, 0.0

        # Find highest exceeded state
        best_state = 0
        best_prob = 0.0
        for state in sorted(FRAGILITY.keys(), reverse=True):
            median, beta = FRAGILITY[state]
            z = math.log(pga_g / median) / beta
            prob = norm.cdf(z)
            if prob >= 0.16:  # 16th percentile threshold
                best_state = state
                best_prob = prob
                break
        return best_state, best_prob

    @staticmethod
    def _shaking_probability(pga_g: float) -> float:
        """Map PGA to shaking probability score [0, 1]."""
        # Logistic curve: P(shaking significant) at pga=0.1g → ~0.3, at 0.5g → ~0.9
        return round(1 / (1 + math.exp(-12 * (pga_g - 0.15))), 3)

    # ------------------------------------------------------------------
    @staticmethod
    def _synthetic_bridge_inventory() -> list[dict]:
        """Synthetic NBI-style bridge inventory for CA key corridors."""
        return [
            # I-5 corridor
            {"id": "B001", "name": "I-5 / LA River Crossing",     "lat": 34.0622, "lon": -118.2437, "type": "HWB1", "year_built": 1968},
            {"id": "B002", "name": "I-5 Tejon Pass",              "lat": 34.8225, "lon": -118.8726, "type": "HWB2", "year_built": 1975},
            {"id": "B003", "name": "I-5 / Sacramento River",      "lat": 38.6049, "lon": -121.5005, "type": "HWB3", "year_built": 1983},
            # I-101 / US-101 corridor
            {"id": "B004", "name": "US-101 / Ventura River",      "lat": 34.2781, "lon": -119.2376, "type": "HWB1", "year_built": 1959},
            {"id": "B005", "name": "US-101 / Salinas River",      "lat": 36.0068, "lon": -121.5432, "type": "HWB2", "year_built": 1971},
            {"id": "B006", "name": "US-101 / San Francisco Bay",  "lat": 37.7749, "lon": -122.4194, "type": "HWB4", "year_built": 1936},
            # Bay Area
            {"id": "B007", "name": "Bay Bridge (Oakland)",        "lat": 37.7983, "lon": -122.3778, "type": "HWB4", "year_built": 1936},
            {"id": "B008", "name": "Golden Gate Bridge",          "lat": 37.8199, "lon": -122.4783, "type": "HWB4", "year_built": 1937},
            {"id": "B009", "name": "I-880 / Coliseum",            "lat": 37.7516, "lon": -122.2010, "type": "HWB1", "year_built": 1957},
            # SoCal
            {"id": "B010", "name": "I-10 / San Gabriel River",   "lat": 33.9773, "lon": -118.0309, "type": "HWB1", "year_built": 1964},
            {"id": "B011", "name": "I-405 / Sepulveda Pass",     "lat": 34.0906, "lon": -118.4571, "type": "HWB2", "year_built": 1969},
            {"id": "B012", "name": "I-215 / San Jacinto River",  "lat": 33.9272, "lon": -117.2308, "type": "HWB1", "year_built": 1963},
            # NorCal
            {"id": "B013", "name": "I-80 / American River",      "lat": 38.5816, "lon": -121.4944, "type": "HWB2", "year_built": 1972},
            {"id": "B014", "name": "Hwy-1 / Russian River",      "lat": 38.4283, "lon": -123.1118, "type": "HWB3", "year_built": 1955},
            {"id": "B015", "name": "I-40 / Colorado River",      "lat": 34.6133, "lon": -114.6267, "type": "HWB2", "year_built": 1966},
        ]

    @staticmethod
    def _ny_bridge_inventory() -> list[dict]:
        """Synthetic NBI-style bridge inventory for NY key corridors."""
        return [
            {"id": "B101", "name": "George Washington Bridge",      "lat": 40.8517, "lon": -73.9527, "type": "HWB4", "year_built": 1931},
            {"id": "B102", "name": "Tappan Zee / Mario M. Cuomo Br", "lat": 41.0700, "lon": -73.8740, "type": "HWB4", "year_built": 2017},
            {"id": "B103", "name": "Verrazzano-Narrows Bridge",      "lat": 40.6066, "lon": -74.0447, "type": "HWB4", "year_built": 1964},
            {"id": "B104", "name": "I-90 / Niagara River (Buffalo)", "lat": 42.9408, "lon": -78.7322, "type": "HWB2", "year_built": 1970},
        ]

    @staticmethod
    def _nj_bridge_inventory() -> list[dict]:
        """Synthetic NBI-style bridge inventory for NJ key corridors."""
        return [
            {"id": "B201", "name": "Pulaski Skyway",                 "lat": 40.7335, "lon": -74.0991, "type": "HWB3", "year_built": 1932},
            {"id": "B202", "name": "Driscoll Bridge (GSP / Raritan)","lat": 40.4612, "lon": -74.2932, "type": "HWB2", "year_built": 1953},
            {"id": "B203", "name": "Delaware Memorial Bridge",       "lat": 39.6859, "lon": -75.5071, "type": "HWB4", "year_built": 1951},
        ]
