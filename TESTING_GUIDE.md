# UDIARS — Feature Testing Guide

Quick checklist for exercising every built feature. Run backend (`python main.py`, port 8000) and frontend (`npm start`, port 3000) first.

## 1. Bug fixes from this session

**Panel overlap** — Load the app, then trigger any alert (see Section 5). Confirm the alert banner pushes the map/control-panel row down instead of covering the top of the control panel.

**Map label weight** — Zoom into any city on the map. City names should look like normal-weight text, not bold/blurry white.

**Direction arrows** — Request any route (Section 4). Small triangular arrows should appear along each route line, pointing the way the route travels. Primary route gets more arrows (8) than alternates (5).

## 2. Region & sub-focus navigation

Click each region pill: **CA**, **NJNY**, **ALL**. Map should fly to the right area each time. With **NJNY** selected, click sub-focus **NJ**, **NY**, **Both** — map re-centers accordingly.

## 3. Presets & hazard layers

Use the preset dropdown/buttons in the control panel to load a sample origin/destination. Toggle the MHRM / flood / wildfire / seismic layer checkboxes — each should show/hide its markers on the map independently.

## 4. Routing

Enter or pick an origin and destination, request a route. Confirm you get a primary route (green, thick) plus two alternates (blue dashed, purple dashed), each with a popup showing ETA and max hazard score. Try an address that should fail routing — confirm it falls back to static JSON instead of erroring.

## 5. Demo scenarios (forces a pre-emptive trigger)

- `POST /demo/flood` (or the "Demo: LA-101 Flood" button) — CA flood on US-101. Confirm: red flashing marker on the map, IMMEDIATE alert banner, reroute via I-405/I-5.
- `POST /demo/flood/njny` — NJ flood demo on US-1.
- `POST /demo/flood/all` — both CA and NJNY at once; alert banner should show a combined message.
- `POST /demo/stop` — clears everything; alert banner and flashing marker disappear.

## 6. Wildfire zone override (demo)

`POST /demo/zone/a`, `/b`, `/c`, `/clear` — forces a wildfire zone badge on affected segments; auto-clears after 60s if you don't call `/clear` yourself.

## 7. Live pre-emptive trigger (non-demo)

With no demo active, watch `/hazards` or the WebSocket feed. If any live (or synthetic-fallback) segment crosses flood_prob > 0.65 on its own, `live_pre_emptive_trigger.active` should flip true and an IMMEDIATE alert should appear without you pressing any demo button. (Synthetic data occasionally crosses this threshold on refresh — leave the app open across a few 60s refresh cycles to catch it, or lower the threshold temporarily in `compound_hazard.py` for a forced test.)

## 8. Three-tier interface

Click **T1**, **T2**, **T3** in the sidebar header.
- T1: one route card, plain-language status only.
- T2: all three routes with hazard scores, plus shelters/hospitals list.
- T3: full per-segment MHRM table, SHAP breakdown, 30/60/90-minute flood-probability horizons, economic impact dashboard.

## 9. Explainability (SHAP)

In T2 or T3, open a segment's detail — look for "Top contributing factors" listing stage_rate, rainfall_1hr, soil_moisture_index ranked by weight.

## 10. WebSocket live updates

Open browser dev tools → Network → WS. Confirm `initial_snapshot` on connect, `mhrm_update` every ~60s, `heartbeat` every ~30s if idle. Kill the backend briefly — frontend should show reconnect attempts with backoff, then recover when backend restarts.

## 11. Multi-region generalizability

Repeat Sections 3–5 with the region pill set to **NJNY** instead of CA — same features, different state data, confirming the pipeline isn't CA-only.

## 12. Mobile layout

Resize the browser to a phone width (or use dev tools device mode). Confirm the layout switches to the compact mobile version: collapsed single-alert banner, bottom-sheet style control panel, no overlap.
