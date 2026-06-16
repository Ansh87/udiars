"""
Flood Prediction Model
Random Forest classifier trained on synthetic California flood data.
Features: stage_ft, stage_rate_ft_hr, rainfall_1hr, rainfall_6hr,
          soil_moisture_index, elevation_ft
Output: flood_probability (0–1) per road segment / gauge location.
"""
import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

FEATURES = [
    "stage_ft",
    "stage_rate_ft_hr",
    "rainfall_1hr",
    "rainfall_6hr",
    "soil_moisture_index",
    "elevation_ft",
]

FLOOD_THRESHOLDS = {
    "high": 0.65,
    "medium": 0.35,
    "low": 0.0,
}


class FloodModel:
    """Random Forest flood probability classifier."""

    def __init__(self):
        self.pipeline: Pipeline | None = None
        self._trained = False

    def train(self):
        """Train on synthetic data representative of California flood conditions."""
        logger.info("Training Flood Model on synthetic data …")
        X, y = self._generate_training_data(n=5000)
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )),
        ])
        self.pipeline.fit(X, y)
        self._trained = True
        logger.info("Flood Model trained. Classes: %s", self.pipeline.classes_)

    def predict_proba(self, features: dict) -> float:
        """Return flood probability [0, 1] given a feature dict."""
        if not self._trained:
            raise RuntimeError("Model not trained — call .train() first")
        x = np.array([[
            features.get("stage_ft", 3.0),
            features.get("stage_rate_ft_hr", 0.0),
            features.get("rainfall_1hr", 0.0),
            features.get("rainfall_6hr", 0.0),
            features.get("soil_moisture_index", 0.4),
            features.get("elevation_ft", 100.0),
        ]])
        proba = self.pipeline.predict_proba(x)[0]
        # Index 1 = flood class
        flood_idx = list(self.pipeline.classes_).index(1) if 1 in self.pipeline.classes_ else 1
        return float(proba[flood_idx])

    def classify(self, prob: float) -> str:
        if prob >= FLOOD_THRESHOLDS["high"]:
            return "high"
        elif prob >= FLOOD_THRESHOLDS["medium"]:
            return "medium"
        return "low"

    @staticmethod
    def soil_moisture_index(antecedent_rainfall_6hr: float, prev_smi: float = 0.4) -> float:
        """Approximate soil moisture index from antecedent rainfall."""
        decay = 0.85  # daily decay factor (simplified)
        recharge = min(antecedent_rainfall_6hr * 0.3, 0.5)
        smi = min(1.0, prev_smi * decay + recharge)
        return round(smi, 3)

    # ------------------------------------------------------------------
    # Synthetic data generation
    # ------------------------------------------------------------------
    def _generate_training_data(self, n: int = 5000):
        rng = np.random.default_rng(42)

        # Baseline normal (no-flood) conditions
        stage        = rng.uniform(0.5, 6.0, n)
        stage_rate   = rng.uniform(-0.2, 0.5, n)
        r1hr         = rng.uniform(0.0, 0.5, n)
        r6hr         = rng.uniform(0.0, 2.0, n)
        smi          = rng.uniform(0.1, 0.9, n)
        elevation    = rng.uniform(0.0, 500.0, n)

        # Inject flood events (25% of samples)
        flood_mask = rng.random(n) < 0.25
        stage[flood_mask]        = rng.uniform(8.0, 25.0, flood_mask.sum())
        stage_rate[flood_mask]   = rng.uniform(0.5, 4.0, flood_mask.sum())
        r1hr[flood_mask]         = rng.uniform(0.5, 3.0, flood_mask.sum())
        r6hr[flood_mask]         = rng.uniform(2.0, 10.0, flood_mask.sum())
        smi[flood_mask]          = rng.uniform(0.65, 1.0, flood_mask.sum())
        elevation[flood_mask]    = rng.uniform(0.0, 80.0, flood_mask.sum())  # low-lying

        X = np.column_stack([stage, stage_rate, r1hr, r6hr, smi, elevation])
        y = flood_mask.astype(int)
        return X, y
