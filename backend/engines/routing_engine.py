"""
Graph-Based Routing Engine
Builds a road network graph for Los Angeles + San Francisco Bay Area using OSMnx.
Applies dynamic edge weights from the MHRM and runs Dijkstra / A* to generate:
  - Primary route
  - Alternate Route 1 (independent corridor)
  - Alternate Route 2 (second independent corridor)

Pre-emptive trigger: if flood_prob > 0.65 on any primary route segment → immediate recalc.
Background recalculation every 60 seconds via APScheduler.
"""
import asyncio
import hashlib
import logging
import math
import os
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Traffic density / edge weight constants (Fix 8.1) ──────────────────────
# w(e,t) = T_nominal × (1 + ALPHA_TRAFFIC·TrafficDensity) + BETA_HAZARD·HazardPenalty
ALPHA_TRAFFIC = 0.5
BETA_HAZARD = 5.0


def traffic_density_for_hour(hour: int) -> float:
    """
    Time-of-day traffic density proxy in [0, 1].
    POC simplification: uses datetime.utcnow().hour directly — true
    regional-local-time conversion (per state/timezone) is out of scope.
    """
    if 6 <= hour < 9:
        return 0.75
    if 9 <= hour < 16:
        return 0.35
    if 16 <= hour < 19:
        return 0.85
    if 19 <= hour < 22:
        return 0.20
    return 0.05


try:
    import osmnx as ox
    import networkx as nx
    OSMNX_AVAILABLE = True
    ox.settings.log_console = False
    ox.settings.use_cache = True
    ox.settings.cache_folder = os.getenv("OSMNX_CACHE_DIR", "./cache/osmnx")
except ImportError:
    OSMNX_AVAILABLE = False
    logger.warning("OSMnx not available — using synthetic road graph")

# Pre-emptive reroute threshold
FLOOD_REROUTE_THRESHOLD = 0.65

# Key California locations for POC routing
CA_LOCATIONS = {
    "los_angeles_union_station": (34.0560, -118.2356),
    "lax_airport":               (33.9425, -118.4081),
    "santa_monica":              (34.0195, -118.4912),
    "burbank_airport":           (34.2001, -118.3585),
    "pasadena":                  (34.1478, -118.1445),
    "long_beach_port":           (33.7701, -118.1937),
    "sf_civic_center":           (37.7793, -122.4193),
    "oakland_city_hall":         (37.8044, -122.2711),
    "san_jose_city_hall":        (37.3382, -121.8863),
    "sfo_airport":               (37.6213, -122.3790),
    "berkeley_uc":               (37.8724, -122.2595),
}


class RoutingEngine:
    """OSMnx-backed dynamic routing with hazard-penalized edge weights."""

    def __init__(self):
        self.graph: Optional[Any] = None  # nx.MultiDiGraph
        self.graph_loaded = False
        self._last_route_cache: dict = {}
        self._current_mhrm: Optional[dict] = None
        self.load_error: str = ""

    # ------------------------------------------------------------------
    # Graph loading (called once at startup, runs in thread pool)
    # ------------------------------------------------------------------
    async def load_graph_async(self):
        """Download and cache road network in a background thread."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_graph_sync)

    def _load_graph_sync(self):
        if not OSMNX_AVAILABLE:
            logger.warning("OSMnx unavailable — routing uses synthetic graph")
            self.graph = self._build_synthetic_graph()
            self.graph_loaded = True
            return

        try:
            logger.info("Loading OSMnx road network for LA + Bay Area …")
            t0 = time.perf_counter()

            # Download drive network for two major metro areas
            la_graph = ox.graph_from_place(
                "Los Angeles, California, USA",
                network_type="drive",
                simplify=True,
            )
            sf_graph = ox.graph_from_place(
                "San Francisco Bay Area, California, USA",
                network_type="drive",
                simplify=True,
            )
            self.graph = nx.compose(la_graph, sf_graph)
            elapsed = time.perf_counter() - t0
            logger.info(
                "OSMnx graph loaded: %d nodes, %d edges in %.1fs",
                self.graph.number_of_nodes(),
                self.graph.number_of_edges(),
                elapsed,
            )
            self.graph_loaded = True
            self.load_error = ""
        except Exception as exc:
            self.load_error = str(exc)
            logger.warning("OSMnx graph load failed — using synthetic: %s", exc)
            self.graph = self._build_synthetic_graph()
            self.graph_loaded = True

    # ------------------------------------------------------------------
    # Update edge weights from MHRM
    # ------------------------------------------------------------------
    def apply_mhrm(self, mhrm: dict):
        """Reweight all graph edges based on current hazard map."""
        self._current_mhrm = mhrm
        if self.graph is None:
            return
        if not OSMNX_AVAILABLE or not isinstance(self.graph, object):
            return

        # Build segment lookup: (lat, lon) → hazard_penalty
        penalty_map: dict[tuple, float] = {}
        for feat in mhrm.get("features", []):
            coords = feat["geometry"]["coordinates"]
            hp = feat["properties"].get("hazard_penalty", 0.0)
            penalty_map[(round(coords[1], 2), round(coords[0], 2))] = hp

        # Apply weights to all edges in graph
        for u, v, k, data in self.graph.edges(data=True, keys=True):
            try:
                node_data = self.graph.nodes[u]
                n_lat = round(node_data.get("y", 0), 2)
                n_lon = round(node_data.get("x", 0), 2)
            except (KeyError, TypeError):
                n_lat, n_lon = 0, 0

            hp = penalty_map.get((n_lat, n_lon), 0.0)
            length_km = data.get("length", 500) / 1000
            t_nominal = length_km / 50  # 50 km/h average speed
            # Fix 8.1: time-of-day traffic density proxy instead of a hardcoded value.
            traffic = traffic_density_for_hour(datetime.utcnow().hour)
            w = t_nominal * (1 + ALPHA_TRAFFIC * traffic) + BETA_HAZARD * hp
            self.graph[u][v][k]["udiars_weight"] = w
            self.graph[u][v][k]["hazard_penalty"] = hp
            self.graph[u][v][k]["traffic_density"] = traffic

    # ------------------------------------------------------------------
    # Route computation
    # ------------------------------------------------------------------
    def compute_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict:
        """Return primary + 2 alternate routes as GeoJSON LineStrings."""
        if self.graph is None:
            return self._fallback_routes(origin_lat, origin_lng, dest_lat, dest_lng)

        try:
            return self._compute_osmnx_routes(origin_lat, origin_lng, dest_lat, dest_lng)
        except Exception as exc:
            logger.warning("Route computation failed — using fallback: %s", exc)
            return self._fallback_routes(origin_lat, origin_lng, dest_lat, dest_lng)

    def _compute_osmnx_routes(self, o_lat, o_lng, d_lat, d_lng) -> dict:
        if not OSMNX_AVAILABLE:
            return self._fallback_routes(o_lat, o_lng, d_lat, d_lng)

        orig_node = ox.nearest_nodes(self.graph, o_lng, o_lat)
        dest_node = ox.nearest_nodes(self.graph, d_lng, d_lat)

        weight_key = "udiars_weight" if nx.get_edge_attributes(self.graph, "udiars_weight") else "length"

        routes = []
        # Remove edges on each prior route to force independent corridors
        g = self.graph.copy()
        for i in range(3):
            try:
                path = nx.shortest_path(g, orig_node, dest_node, weight=weight_key)
                coords = [
                    [g.nodes[n]["x"], g.nodes[n]["y"]]
                    for n in path
                    if "x" in g.nodes[n] and "y" in g.nodes[n]
                ]
                hp_values = [
                    g.edges[path[j], path[j+1], 0].get("hazard_penalty", 0.0)
                    for j in range(len(path) - 1)
                    if g.has_edge(path[j], path[j+1])
                ]
                max_hp = max(hp_values, default=0.0)

                # Remove intermediate edges to force alternate corridors
                if i < 2:
                    mid = len(path) // 2
                    segment = path[mid - 5: mid + 5]
                    for j in range(len(segment) - 1):
                        if g.has_edge(segment[j], segment[j + 1]):
                            g.remove_edge(segment[j], segment[j + 1])

                routes.append({
                    "type":          ["primary", "alternate_1", "alternate_2"][i],
                    "coordinates":   coords,
                    "node_count":    len(path),
                    "max_hazard_penalty": round(max_hp, 3),
                    "pre_emptive_trigger": max_hp >= FLOOD_REROUTE_THRESHOLD,
                    "eta_minutes":   round(len(coords) * 0.15, 0),  # rough proxy
                })
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                break

        return self._format_route_response(o_lat, o_lng, d_lat, d_lng, routes)

    # ------------------------------------------------------------------
    def check_pre_emptive_trigger(self, route: dict) -> bool:
        """Return True if any segment on the primary route exceeds flood threshold."""
        if route.get("max_hazard_penalty", 0.0) >= FLOOD_REROUTE_THRESHOLD:
            return True
        return False

    # ------------------------------------------------------------------
    # Synthetic graph (fallback when OSMnx is unavailable / slow)
    # ------------------------------------------------------------------
    def _build_synthetic_graph(self):
        """Build a lightweight synthetic CA road network for POC demos."""
        if not OSMNX_AVAILABLE:
            # Return a minimal dict-based representation
            return None

        G = nx.DiGraph()
        nodes = [
            (0,  {"y": 34.0560, "x": -118.2356, "name": "LA Union Station"}),
            (1,  {"y": 33.9425, "x": -118.4081, "name": "LAX"}),
            (2,  {"y": 34.0195, "x": -118.4912, "name": "Santa Monica"}),
            (3,  {"y": 34.1478, "x": -118.1445, "name": "Pasadena"}),
            (4,  {"y": 33.7701, "x": -118.1937, "name": "Long Beach"}),
            (5,  {"y": 34.2001, "x": -118.3585, "name": "Burbank"}),
            (6,  {"y": 34.4208, "x": -119.6982, "name": "Santa Barbara"}),
            (7,  {"y": 34.9530, "x": -120.4357, "name": "San Luis Obispo"}),
            (8,  {"y": 36.0068, "x": -121.5432, "name": "Salinas"}),
            (9,  {"y": 37.3382, "x": -121.8863, "name": "San Jose"}),
            (10, {"y": 37.6213, "x": -122.3790, "name": "SFO"}),
            (11, {"y": 37.7793, "x": -122.4193, "name": "SF Civic Ctr"}),
            (12, {"y": 37.8044, "x": -122.2711, "name": "Oakland"}),
            (13, {"y": 37.8724, "x": -122.2595, "name": "Berkeley"}),
        ]
        G.add_nodes_from(nodes)
        edges = [
            (0, 1), (1, 2), (0, 3), (0, 4), (0, 5),  # LA metro
            (5, 6), (6, 7), (7, 8), (8, 9),            # US-101 N
            (9, 10), (10, 11), (11, 12), (12, 13),     # Bay Area
            (1, 0), (2, 1), (3, 0), (4, 0), (5, 0),   # reverse
            (6, 5), (7, 6), (8, 7), (9, 8),
            (10, 9), (11, 10), (12, 11), (13, 12),
        ]
        for u, v in edges:
            nu, nv = dict(nodes)[u], dict(nodes)[v]
            d = self._haversine_km(nu["y"], nu["x"], nv["y"], nv["x"])
            G.add_edge(u, v, length=d * 1000, udiars_weight=d / 50, hazard_penalty=0.0)
        return G

    # ------------------------------------------------------------------
    # Fallback routes (straight-line decomposed)
    # ------------------------------------------------------------------
    def _fallback_routes(self, o_lat, o_lng, d_lat, d_lng) -> dict:
        """Return three interpolated straight-line routes as GeoJSON."""
        def lerp_route(offset_lat=0.0, offset_lon=0.0, n=20):
            return [
                [o_lng + (d_lng - o_lng) * i / n + offset_lon,
                 o_lat + (d_lat - o_lat) * i / n + offset_lat]
                for i in range(n + 1)
            ]

        routes = [
            {"type": "primary",     "coordinates": lerp_route(), "max_hazard_penalty": 0.1, "pre_emptive_trigger": False, "eta_minutes": 30},
            {"type": "alternate_1", "coordinates": lerp_route(0.05, -0.03), "max_hazard_penalty": 0.05, "pre_emptive_trigger": False, "eta_minutes": 35},
            {"type": "alternate_2", "coordinates": lerp_route(-0.05, 0.02), "max_hazard_penalty": 0.08, "pre_emptive_trigger": False, "eta_minutes": 40},
        ]
        return self._format_route_response(o_lat, o_lng, d_lat, d_lng, routes)

    def _format_route_response(self, o_lat, o_lng, d_lat, d_lng, routes) -> dict:
        features = []
        styles = {
            "primary":     {"color": "#00CC44", "weight": 6, "dashArray": None},
            "alternate_1": {"color": "#2196F3", "weight": 4, "dashArray": "8,4"},
            "alternate_2": {"color": "#9C27B0", "weight": 4, "dashArray": "4,4"},
        }
        for r in routes:
            rtype = r["type"]
            style = styles.get(rtype, {})
            trigger = r.get("pre_emptive_trigger", False)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": r["coordinates"],
                },
                "properties": {
                    "route_type":         rtype,
                    "max_hazard_penalty": r.get("max_hazard_penalty", 0.0),
                    "pre_emptive_trigger": trigger,
                    "eta_minutes":        r.get("eta_minutes", 30),
                    "color":              "#FF0000" if trigger else style.get("color", "#666"),
                    "weight":             style.get("weight", 4),
                    "dashArray":          style.get("dashArray"),
                    "alert_message":      (
                        "⚠️ Flood risk detected — pre-emptive rerouting active"
                        if trigger else ""
                    ),
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
            "origin":      {"lat": o_lat, "lng": o_lng},
            "destination": {"lat": d_lat, "lng": d_lng},
            "computed_at": datetime.utcnow().isoformat(),
            "graph_loaded": self.graph_loaded,
        }

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2) -> float:
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
