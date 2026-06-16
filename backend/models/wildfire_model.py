"""
Wildfire Risk Model
XGBoost multi-class classifier for ignition probability and zone classification.
Zone A: within 2 miles of active fire (score 1.0)
Zone B: 2-10 miles from active fire (score 0.6)
Zone C: 10-25 miles from active fire (score 0.3)
No zone: >25 miles (score 0.0)

Features: distance_to_fire_km, wind_speed_mph, temperature_f,
          relative_humidity_pct, frp_mw, ndvi_proxy, elevation_ft
"""
import logging
import math
import numpy as np

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from sklearn.ensemble import GradientBoostingClassifier  # fallback

logger = logging.getLogger(__name__)

# Zone boundaries in km (approx miles → km conversion)
ZONE_A_KM  = 3.2    # 2 miles
ZONE_B_KM  = 16.1   # 10 miles
ZONE_C_KM  = 40.2   # 25 miles

ZONE_SCORES = {0: 0.0, 1: 0.3, 2: 0.6, 3: 1.0}  # no-zone, C, B, A
ZONE_LABELS = {0: "none", 1: "C", 2: "B", 3: "A"}


class WildfireModel:
    """XGBoost wildfire zone + ignition probability classifier."""

    def __init__(self):
        self.model = None
        self._trained = False

    def train(self):
        logger.info("Training Wildfire Model on synthetic data …")
        X, y = self._generate_training_data(n=6000)
        if XGB_AVAILABLE:
            self.model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.08,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric="mlogloss",
                random_state=42,
                n_jobs=-1,
            )
        else:
            logger.warning("XGBoost not available — using GradientBoosting fallback")
            self.model = GradientBoostingClassifier(
                n_estimators=150,
                max_depth=5,
                learning_rate=0.08,
                random_state=42,
            )
        self.model.fit(X, y)
        self._trained = True
        logger.info("Wildfire Model trained.")

    def predict(self, features: dict) -> dict:
        """
        Returns zone label (A/B/C/none), zone_score (0–1),
        and ignition_probability (0–1).
        """
        if not self._trained:
            raise RuntimeError("Model not trained — call .train() first")

        x = np.array([[
            features.get("distance_to_fire_km", 50.0),
            features.get("wind_speed_mph", 10.0),
            features.get("temperature_f", 75.0),
            features.get("relative_humidity_pct", 40.0),
            features.get("frp_mw", 0.0),
            features.get("ndvi_proxy", 0.5),
            features.get("elevation_ft", 200.0),
        ]])

        zone_class = int(self.model.predict(x)[0])
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(x)[0]
            ignition_prob = float(proba[zone_class])
        else:
            ignition_prob = ZONE_SCORES[zone_class]

        # Also compute a direct geometric zone score
        dist_km = features.get("distance_to_fire_km", 50.0)
        geo_zone = self._geo_zone(dist_km)

        # Blend model + geometric
        final_score = max(ZONE_SCORES.get(zone_class, 0.0),
                          ZONE_SCORES.get(geo_zone, 0.0))

        return {
            "zone": ZONE_LABELS.get(geo_zone, "none"),
            "zone_score": round(final_score, 3),
            "ignition_probability": round(ignition_prob, 3),
        }

    @staticmethod
    def _geo_zone(dist_km: float) -> int:
        if dist_km <= ZONE_A_KM:
            return 3
        elif dist_km <= ZONE_B_KM:
            return 2
        elif dist_km <= ZONE_C_KM:
            return 1
        return 0

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in km."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi  = math.radians(lat2 - lat1)
        dlam  = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def nearest_fire_distance(self, lat: float, lon: float, fires: list[dict]) -> float:
        """Return distance in km to nearest active fire detection."""
        if not fires:
            return 999.0
        return min(
            self.haversine_km(lat, lon, f["lat"], f["lon"])
            for f in fires
        )

    # ------------------------------------------------------------------
    def _generate_training_data(self, n: int = 6000):
        rng = np.random.default_rng(7)
        dist    = rng.uniform(0, 60, n)
        wind    = rng.uniform(0, 50, n)
        temp    = rng.uniform(55, 115, n)
        rh      = rng.uniform(5, 80, n)
        frp     = rng.uniform(0, 100, n)
        ndvi    = rng.uniform(0, 1, n)
        elev    = rng.uniform(0, 3000, n)

        X = np.column_stack([dist, wind, temp, rh, frp, ndvi, elev])

        # Label by geometry + weather modifiers
        y = np.zeros(n, dtype=int)
        y[dist <= ZONE_A_KM]  = 3
        y[(dist > ZONE_A_KM) & (dist <= ZONE_B_KM)] = 2
        y[(dist > ZONE_B_KM) & (dist <= ZONE_C_KM)] = 1

        # Bump some Zone-C → Zone-B under extreme conditions
        extreme = (wind > 30) & (rh < 15) & (temp > 95)
        y[(y == 1) & extreme] = 2

        return X, y
