/**
 * MapView — full-screen Leaflet map with hazard overlays and route lines.
 *
 * Overlays:
 *   - MHRM segments: color-coded circles (green→yellow→orange→red)
 *   - Fire perimeters: orange/red markers for active fire detections
 *   - Flood risk: blue semi-transparent circles on high-risk segments
 *   - Seismic risk: purple circles proportional to PGA
 *   - Primary route:     thick green solid line
 *   - Alternate Route 1: blue dashed line
 *   - Alternate Route 2: purple dashed line
 */
import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { STATE_CONFIG, REGION_PILLS, SUB_FOCUS } from '../constants/appData';

// "flood"->"Flood-Dominant", "wildfire"->"Wildfire-Dominant", "seismic"->"Seismic-Dominant",
// "compound"->"Compound Hazard" — per Fix 7 spec.
function dominantHazardLabel(dh) {
  if (!dh) return null;
  if (dh === 'compound') return 'Compound Hazard';
  const cap = dh.charAt(0).toUpperCase() + dh.slice(1);
  return `${cap}-Dominant`;
}

const HAZARD_PENALTY_TOOLTIP =
  'HazardPenalty = max(flood_prob, wildfire_zone_score, seismic_pga_score) per UDIARS patent ' +
  'Section 4.7 — w(e,t) = T_nominal×(1+0.5×Traffic)+5.0×HazardPenalty';

function stageDirection(stageRate) {
  if (stageRate === undefined || stageRate === null) return '';
  if (stageRate > 0.05) return ' ↑ Rising';
  if (stageRate < -0.05) return ' ↓ Falling';
  return ' → Stable';
}

// Fix Leaflet's default icon paths broken by webpack
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const CA_CENTER = STATE_CONFIG.CA.center;
const CA_ZOOM   = STATE_CONFIG.CA.zoom;

export default function MapView({ mhrm, routes, hazardVisibility, region, regionPill, subFocus, demoState }) {
  const mapRef       = useRef(null);
  const leafletRef   = useRef(null);
  const layersRef    = useRef({
    mhrm:     null,
    flood:    null,
    wildfire: null,
    seismic:  null,
    routes:   null,
  });
  const demoMarkerRef    = useRef(null);
  const demoIntervalRef  = useRef(null);

  // Initialize map once
  useEffect(() => {
    if (leafletRef.current) return;

    const map = L.map(mapRef.current, {
      center: CA_CENTER,
      zoom: CA_ZOOM,
      // Zoom control defaults to top-left, which collides with the
      // ControlPanel overlay anchored there — move it out of the way.
      zoomControl: false,
      attributionControl: true,
    });
    L.control.zoom({ position: 'topright' }).addTo(map);

    // Dark basemap WITHOUT labels, so we can overlay bright labels on top
    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
      {
        attribution: '©OpenStreetMap ©CartoDB',
        subdomains: 'abcd',
        maxZoom: 18,
      }
    ).addTo(map);

    // Dedicated high-zIndex pane for labels so they always stay legible above markers
    const labelsPane = map.createPane('labelsPane');
    labelsPane.style.zIndex = 650;
    labelsPane.style.pointerEvents = 'none';

    // Bright city/place name labels overlay (brightness-boosted via CSS filter)
    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png',
      {
        subdomains: 'abcd',
        maxZoom: 18,
        pane: 'labelsPane',
        className: 'bright-map-labels',
      }
    ).addTo(map);

    // Legend
    const legend = L.control({ position: 'bottomleft' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div');
      div.style.cssText = `
        background: rgba(13,27,42,0.92);
        border: 1px solid #1e3a5c;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 12px;
        color: #e2e8f0;
        line-height: 1.8;
        max-width: 220px;
      `;
      div.innerHTML = `
        <b style="font-size:11px;letter-spacing:.08em;color:#94a3b8">COMPOUND RISK LEVEL</b><br>
        <span style="font-size:10px;color:#64748b">Combined score per road segment: worst of flood + wildfire + seismic risk</span><br>
        <span style="color:#22c55e">●</span> Low (&lt;15%)<br>
        <span style="color:#eab308">●</span> Medium (15–35%)<br>
        <span style="color:#f97316">●</span> High (35–65%)<br>
        <span style="color:#ef4444">●</span> Critical (&gt;65%)<br>
        <hr style="border-color:#2d4a6e;margin:6px 0">
        <b style="font-size:11px;letter-spacing:.08em;color:#94a3b8">ROUTES</b><br>
        <span style="color:#22c55e">━━</span> Primary<br>
        <span style="color:#3b82f6">╌╌</span> Alternate 1<br>
        <span style="color:#a855f7">┄┄</span> Alternate 2
      `;
      return div;
    };
    legend.addTo(map);

    leafletRef.current = map;
    return () => {
      map.remove();
      leafletRef.current = null;
    };
  }, []);

  // Zoom/pan — pill-level regions (CA/NJNY/ALL) use flyTo with the three named
  // targets from Fix 3; NJNY sub-state focus (NJ/NY/BOTH) overrides with its
  // own flyTo target. Falls back to the legacy per-state fitBounds behavior
  // when only the old single-state `region` prop is supplied (no regionPill).
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;

    if (regionPill) {
      let target = REGION_PILLS[regionPill];
      if (regionPill === 'NJNY' && subFocus && SUB_FOCUS[subFocus]) {
        target = SUB_FOCUS[subFocus];
      }
      if (target) {
        try {
          map.flyTo(target.center, target.zoom, { duration: 1.2 });
        } catch (_) {
          map.setView(target.center, target.zoom);
        }
        return;
      }
    }

    if (!region) return;
    const cfg = STATE_CONFIG[region];
    if (!cfg) return;
    try {
      map.fitBounds(cfg.bounds, { padding: [20, 20] });
    } catch (_) {
      map.setView(cfg.center, cfg.zoom);
    }
  }, [region, regionPill, subFocus]);

  // MHRM overlay
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;

    if (layersRef.current.mhrm) {
      layersRef.current.mhrm.remove();
      layersRef.current.mhrm = null;
    }
    if (layersRef.current.flood) {
      layersRef.current.flood.remove();
      layersRef.current.flood = null;
    }
    if (layersRef.current.wildfire) {
      layersRef.current.wildfire.remove();
      layersRef.current.wildfire = null;
    }
    if (layersRef.current.seismic) {
      layersRef.current.seismic.remove();
      layersRef.current.seismic = null;
    }

    if (!mhrm?.features?.length) return;

    const mhrmGroup    = L.layerGroup();
    const floodGroup   = L.layerGroup();
    const wfGroup      = L.layerGroup();
    const seismicGroup = L.layerGroup();

    for (const feat of mhrm.features) {
      const coords = feat.geometry?.coordinates;
      if (!coords) continue;
      const [lon, lat] = coords;
      const p = feat.properties;

      // ── MHRM segment marker ──
      if (hazardVisibility.mhrm) {
        const hp = p.hazard_penalty || 0;
        const radius = 14 + hp * 20;
        const circle = L.circleMarker([lat, lon], {
          radius,
          color:     p.risk_color || '#22c55e',
          fillColor: p.risk_color || '#22c55e',
          fillOpacity: 0.35,
          weight: 2,
          opacity: 0.8,
        });
        const dhLabel = dominantHazardLabel(p.dominant_hazard);
        const stageArrow = stageDirection(p.stage_rate_ft_hr);
        // Tier gate for 30/60/90 horizons is applied in Sidebar (T2/T3 only);
        // the map popup always shows them when present since map popups aren't tier-scoped.
        const horizonsLine = (p.flood_prob_30 !== undefined || p.flood_prob_60 !== undefined || p.flood_prob_90 !== undefined)
          ? `<span style="color:#60a5fa;font-size:10px">P(flood) t+30: ${((p.flood_prob_30||0)*100).toFixed(0)}% · t+60: ${((p.flood_prob_60||0)*100).toFixed(0)}% · t+90: ${((p.flood_prob_90||0)*100).toFixed(0)}%</span><br>`
          : '';
        circle.bindPopup(`
          <div style="font-family:monospace;font-size:12px;min-width:220px">
            <b>${p.name}</b><br>
            <span style="color:#94a3b8">Highway:</span> ${p.highway} · ${p.direction}<br>
            <hr style="border-color:#334">
            <b style="color:${p.risk_color}" title="${HAZARD_PENALTY_TOOLTIP}">Compound Risk: ${(hp*100).toFixed(0)}% (${p.risk_level?.toUpperCase()})${dhLabel ? ' · ' + dhLabel : ''} ⓘ</b><br>
            <span style="color:#64748b;font-size:10px">= worst of flood / wildfire / seismic below</span><br>
            <span style="color:#60a5fa">🌊 Flood:</span> ${(p.flood_probability*100).toFixed(1)}% · Stage: ${p.stage_ft}ft${stageArrow}<br>
            ${horizonsLine}
            <span style="color:#fb923c">🔥 Wildfire:</span> Zone ${p.wildfire_zone || 'none'} · ${p.dist_to_fire_km}km to fire<br>
            <span style="color:#c084fc">🌍 Seismic:</span> PGA ${p.seismic_pga_g}g · ${p.seismic_damage}<br>
            <span style="color:#94a3b8">Edge Weight:</span> ${p.edge_weight}<br>
            <span style="color:#475569;font-size:10px">${p.updated_at}</span>
          </div>
        `, { maxWidth: Math.min(280, window.innerWidth * 0.9) });
        mhrmGroup.addLayer(circle);
      }

      // ── Flood overlay ──
      if (hazardVisibility.flood && p.flood_probability >= 0.15) {
        const fp = p.flood_probability;
        const fCircle = L.circleMarker([lat, lon], {
          radius:      8 + fp * 18,
          color:       '#3b82f6',
          fillColor:   '#3b82f6',
          fillOpacity: fp * 0.5,
          weight: 1,
          opacity: 0.6,
        });
        fCircle.bindTooltip(`Flood: ${(fp*100).toFixed(0)}%`, { permanent: false });
        floodGroup.addLayer(fCircle);
      }

      // ── Wildfire overlay ──
      if (hazardVisibility.wildfire && p.wildfire_zone !== 'none') {
        const zoneColors = { A: '#ef4444', B: '#f97316', C: '#eab308' };
        const zColor = zoneColors[p.wildfire_zone] || '#eab308';
        const wCircle = L.circleMarker([lat, lon], {
          radius:      p.wildfire_zone === 'A' ? 16 : p.wildfire_zone === 'B' ? 12 : 8,
          color:       zColor,
          fillColor:   zColor,
          fillOpacity: 0.25,
          weight: 1.5,
          opacity: 0.7,
        });
        wCircle.bindTooltip(`🔥 Zone ${p.wildfire_zone}`, { permanent: false });
        wfGroup.addLayer(wCircle);
      }

      // ── Seismic overlay ──
      if (hazardVisibility.seismic && p.seismic_pga_g > 0.02) {
        const pga = Math.min(p.seismic_pga_g, 1.0);
        const sCircle = L.circleMarker([lat, lon], {
          radius:      6 + pga * 20,
          color:       '#a855f7',
          fillColor:   '#a855f7',
          fillOpacity: pga * 0.4,
          weight: 1,
          opacity: 0.6,
        });
        sCircle.bindTooltip(`🌍 PGA: ${p.seismic_pga_g}g`, { permanent: false });
        seismicGroup.addLayer(sCircle);
      }
    }

    if (hazardVisibility.mhrm)    { mhrmGroup.addTo(map);    layersRef.current.mhrm     = mhrmGroup;    }
    if (hazardVisibility.flood)   { floodGroup.addTo(map);   layersRef.current.flood    = floodGroup;   }
    if (hazardVisibility.wildfire){ wfGroup.addTo(map);      layersRef.current.wildfire = wfGroup;      }
    if (hazardVisibility.seismic) { seismicGroup.addTo(map); layersRef.current.seismic  = seismicGroup; }
  }, [mhrm, hazardVisibility]);

  // Route overlay
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;
    if (layersRef.current.routes) { layersRef.current.routes.remove(); layersRef.current.routes = null; }
    if (!routes?.features?.length) return;

    const routeGroup = L.layerGroup();
    const bounds = [];

    for (const feat of routes.features) {
      const coords = feat.geometry?.coordinates;
      if (!coords?.length) continue;
      const p = feat.properties;
      const latLngs = coords.map(([lon, lat]) => [lat, lon]);
      bounds.push(...latLngs);

      const isTrigger = p.pre_emptive_trigger;
      const style = {
        color:     isTrigger ? '#FF0000' : (p.color || '#22c55e'),
        weight:    p.weight || 4,
        opacity:   0.9,
        dashArray: p.dashArray || null,
      };

      const line = L.polyline(latLngs, style);

      // Add animated arrows for primary route
      if (p.route_type === 'primary') {
        line.setStyle({ weight: 6 });
      }

      const popupContent = `
        <div style="font-family:monospace;font-size:12px">
          <b>${p.route_type === 'primary' ? '🟢 Primary Route' : p.route_type === 'alternate_1' ? '🔵 Alternate 1' : '🟣 Alternate 2'}</b><br>
          ETA: <b>${p.eta_minutes} min</b><br>
          Max Hazard: <b style="color:${isTrigger ? '#ef4444' : '#22c55e'}">${(p.max_hazard_penalty * 100).toFixed(0)}%</b><br>
          ${isTrigger ? `<span style="color:#ef4444">${p.alert_message}</span>` : '✅ Clear'}
        </div>
      `;
      line.bindPopup(popupContent, { maxWidth: Math.min(260, window.innerWidth * 0.9) });

      // Origin / destination markers
      if (latLngs.length > 0 && p.route_type === 'primary') {
        L.circleMarker(latLngs[0], { radius: 8, color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1, weight: 3 })
          .bindTooltip('📍 Origin')
          .addTo(routeGroup);
        L.circleMarker(latLngs[latLngs.length - 1], { radius: 8, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 1, weight: 3 })
          .bindTooltip('🏁 Destination')
          .addTo(routeGroup);
      }

      routeGroup.addLayer(line);
    }

    routeGroup.addTo(map);
    layersRef.current.routes = routeGroup;

    // Fit map to route bounds
    if (bounds.length > 1) {
      try { map.fitBounds(bounds, { padding: [40, 40] }); } catch (_) {}
    }
  }, [routes]);

  // Demo flood flash marker (Fix 6) — flashes red/dark every 800ms at the
  // demo's flooded segment while active. Tries to cross-reference the MHRM
  // feature by segment name; falls back to a fixed marker near the pill's
  // region center if no clean match is found (best-effort, POC-level).
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;

    const clearDemoMarker = () => {
      if (demoIntervalRef.current) { clearInterval(demoIntervalRef.current); demoIntervalRef.current = null; }
      if (demoMarkerRef.current)   { demoMarkerRef.current.remove(); demoMarkerRef.current = null; }
    };

    if (!demoState?.active) { clearDemoMarker(); return; }

    const segmentName = demoState.segment || demoState.reroute?.reason;
    let coords = null;
    if (segmentName && mhrm?.features?.length) {
      const match = mhrm.features.find(f =>
        f.properties?.name && segmentName.toLowerCase().includes(f.properties.name.toLowerCase())
      );
      if (match?.geometry?.coordinates) {
        const [lon, lat] = match.geometry.coordinates;
        coords = [lat, lon];
      }
    }
    // Fallback: fixed marker at the active pill's center if no MHRM cross-reference found.
    if (!coords) {
      const cfg = REGION_PILLS[demoState.region?.toUpperCase?.()] || REGION_PILLS.CA;
      coords = cfg.center;
    }

    clearDemoMarker();
    const marker = L.circleMarker(coords, {
      radius: 16, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.6, weight: 3,
    }).bindTooltip(`🚨 ${segmentName || 'Flood event'}`, { permanent: false });
    marker.addTo(map);
    demoMarkerRef.current = marker;

    let toggled = false;
    demoIntervalRef.current = setInterval(() => {
      toggled = !toggled;
      const color = toggled ? '#1f2937' : '#ef4444';
      marker.setStyle({ color, fillColor: color });
    }, 800);

    return clearDemoMarker;
  }, [demoState, mhrm]);

  return (
    <div
      ref={mapRef}
      style={{
        flex: 1,
        height: '100%',
        background: '#0a1628',
      }}
    />
  );
}
