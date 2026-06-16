"""
Economic Impact Engine
Applies HAZUS-MH simplified fragility curves to estimate bridge damage costs.
Also provides a summary economic impact report for affected road segments.

Damage States: None | Slight | Moderate | Extensive | Complete
Cost factors based on HAZUS-MH 2.1 Table 15.9 (simplified).
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# HAZUS-MH replacement cost factors by damage state
DAMAGE_STATE_COST_FACTOR = {
    "None":      0.000,
    "Slight":    0.030,
    "Moderate":  0.080,
    "Extensive": 0.250,
    "Complete":  1.000,
}

# Business interruption days per damage state
BUSINESS_INTERRUPTION_DAYS = {
    "None":      0,
    "Slight":    3,
    "Moderate":  30,
    "Extensive": 90,
    "Complete":  365,
}

# Daily economic cost of closure per major highway (USD millions)
HIGHWAY_DAILY_COST_M = {
    "I-5":    2.5,
    "US-101": 1.8,
    "I-405":  2.1,
    "I-10":   2.0,
    "I-80":   1.5,
    "I-880":  1.2,
    "CA-99":  0.8,
    "I-580":  1.1,
}


class EconomicImpactEngine:
    """Compute infrastructure damage costs and business interruption losses."""

    def __init__(self, seismic_model):
        self.seismic_model = seismic_model

    def compute_report(
        self,
        mhrm: dict,
        earthquakes: list[dict],
        demo_state: dict | None = None,
    ) -> dict:
        """
        Returns a full economic impact report covering:
        - Bridge damage inventory
        - Highway closure costs
        - Total estimated economic loss
        """
        bridge_damage = self.seismic_model.affected_bridges(earthquakes, radius_km=80)

        # Enhance with replacement cost estimates
        bridge_records = []
        total_bridge_loss_m = 0.0
        for b in bridge_damage:
            state = b.get("damage_label", "None")
            factor = DAMAGE_STATE_COST_FACTOR.get(state, 0.0)
            replacement_m = {"HWB1": 8.5, "HWB2": 12.0, "HWB3": 6.0, "HWB4": 20.0}.get(
                b.get("type", "HWB1"), 8.5
            )
            loss_m = round(replacement_m * factor, 2)
            total_bridge_loss_m += loss_m

            bridge_records.append({
                "bridge_id":       b["id"],
                "bridge_name":     b["name"],
                "lat":             b["lat"],
                "lon":             b["lon"],
                "type":            b.get("type", "HWB1"),
                "year_built":      b.get("year_built", 1970),
                "damage_state":    b.get("damage_state", 0),
                "damage_label":    state,
                "damage_prob":     b.get("damage_probability", 0.0),
                "pga_g":           b.get("pga_g", 0.0),
                "replacement_m":   replacement_m,
                "estimated_loss_m": loss_m,
                "days_closure":    BUSINESS_INTERRUPTION_DAYS.get(state, 0),
            })

        # Segment-level highway closure costs from MHRM
        closure_records = []
        total_closure_loss_m = 0.0
        for feat in mhrm.get("features", []):
            props = feat["properties"]
            hp = props.get("hazard_penalty", 0.0)
            if hp < 0.35:
                continue
            highway = props.get("highway", "")
            daily_cost = HIGHWAY_DAILY_COST_M.get(highway, 0.5)

            if hp >= 0.65:
                risk_level = "Critical"
                closure_days = 14
            elif hp >= 0.35:
                risk_level = "High"
                closure_days = 3
            else:
                risk_level = "Medium"
                closure_days = 1

            est_loss = round(daily_cost * closure_days * hp, 2)
            total_closure_loss_m += est_loss

            closure_records.append({
                "segment_id":    props.get("id", ""),
                "segment_name":  props.get("name", ""),
                "highway":       highway,
                "risk_level":    risk_level,
                "hazard_penalty": hp,
                "flood_prob":    props.get("flood_probability", 0.0),
                "wildfire_zone": props.get("wildfire_zone", "none"),
                "seismic_damage": props.get("seismic_damage", "None"),
                "est_closure_days": closure_days,
                "daily_cost_m":  daily_cost,
                "estimated_loss_m": est_loss,
            })

        # Demo mode: inject extra losses for I-101 LA flood scenario
        if demo_state and demo_state.get("active"):
            demo_loss = {
                "segment_id":    "DEMO-101-FLOOD",
                "segment_name":  "US-101 (LA Demo Flood Scenario)",
                "highway":       "US-101",
                "risk_level":    "Critical",
                "hazard_penalty": 0.92,
                "flood_prob":    0.92,
                "wildfire_zone": "none",
                "seismic_damage": "None",
                "est_closure_days": 21,
                "daily_cost_m":  1.8,
                "estimated_loss_m": 34.56,
                "note": "DEMO MODE — simulated flood event",
            }
            closure_records.insert(0, demo_loss)
            total_closure_loss_m += 34.56

        grand_total_m = round(total_bridge_loss_m + total_closure_loss_m, 2)

        return {
            "summary": {
                "total_bridges_affected":  len(bridge_records),
                "total_bridge_loss_m":     round(total_bridge_loss_m, 2),
                "total_closure_loss_m":    round(total_closure_loss_m, 2),
                "grand_total_loss_m":      grand_total_m,
                "grand_total_loss_b":      round(grand_total_m / 1000, 4),
                "segments_at_risk":        len(closure_records),
                "critical_segments":       sum(1 for r in closure_records if r["risk_level"] == "Critical"),
                "generated_at":            datetime.utcnow().isoformat(),
            },
            "bridge_damage":   bridge_records,
            "highway_closures": closure_records,
        }
