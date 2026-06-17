/**
 * Sidebar — three-tier progressive disclosure interface.
 * Tier 1: Driver — simple route card + plain language alert + ETA
 * Tier 2: First Responder — all routes with hazard scores + shelters
 * Tier 3: Emergency Manager — full MHRM per-segment data + economic dashboard
 */
import React, { useState } from 'react';
import EconomicDashboard from './EconomicDashboard';
import { TIER_INFO } from '../constants/appData';

const TIER_LABELS = TIER_INFO.map(t => t.label);

// Static fallback shelter/hospital list — used only if the /facilities
// endpoint hasn't returned data yet (e.g. backend briefly unavailable).
const FALLBACK_SHELTERS = [
  { name: 'LA Convention Center', lat: 34.0430, lng: -118.2673, type: 'Shelter', capacity: 5000 },
  { name: 'Rose Bowl Stadium',    lat: 34.1614, lng: -118.1676, type: 'Shelter', capacity: 20000 },
  { name: 'Dodger Stadium',       lat: 34.0739, lng: -118.2400, type: 'Shelter', capacity: 56000 },
  { name: 'Cedars-Sinai Hospital',lat: 34.0756, lng: -118.3793, type: 'Hospital', beds: 886 },
  { name: 'UCLA Medical Center',  lat: 34.0664, lng: -118.4455, type: 'Hospital', beds: 520 },
  { name: 'SF Moscone Center',    lat: 37.7841, lng: -122.4005, type: 'Shelter', capacity: 10000 },
  { name: 'SF General Hospital',  lat: 37.7552, lng: -122.4058, type: 'Hospital', beds: 420 },
];

function HazardBar({ label, value, color }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
        <span style={{ color: '#94a3b8' }}>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  );
}

// "flood"->"Flood-Dominant", "compound"->"Compound Hazard" etc. (Fix 7)
function dominantHazardLabel(dh) {
  if (!dh) return null;
  if (dh === 'compound') return 'Compound Hazard';
  const cap = dh.charAt(0).toUpperCase() + dh.slice(1);
  return `${cap}-Dominant`;
}

const HAZARD_PENALTY_TOOLTIP =
  'HazardPenalty = max(flood_prob, wildfire_zone_score, seismic_pga_score) per UDIARS patent ' +
  'Section 4.7 — w(e,t) = T_nominal×(1+0.5×Traffic)+5.0×HazardPenalty';

function SHAPBreakdown({ features, approximation = false }) {
  if (!features?.length) return null;
  const sorted = [...features].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0));
  return (
    <div style={{ marginTop: 6, fontSize: 11 }}>
      <div style={{ color: '#94a3b8', fontWeight: 600, marginBottom: 3 }}>
        SHAP Feature Attribution {approximation ? '(POC approximation)' : ''}
      </div>
      {sorted.slice(0, 3).map((f, i) => (
        <div key={f.feature || i} style={{ color: '#cbd5e1' }}>
          {i + 1}. {f.feature} = {f.value} (weight: {f.weight})
        </div>
      ))}
    </div>
  );
}

// Client-side synthesized SHAP-style breakdown for demo mode when the backend
// doesn't supply numeric values — explicitly labeled as a POC approximation.
function synthesizeDemoSHAP(demoState) {
  const stageRate = demoState?.stage_rate_ft_hr ?? 0.8;
  const rainfall = demoState?.rainfall_1hr_in ?? 0.6;
  const soil = demoState?.soil_moisture_index ?? 0.4;
  const total = stageRate + rainfall + soil || 1;
  return [
    { feature: 'stage_rate_ft_hr',     value: stageRate, weight: +(stageRate / total).toFixed(2) },
    { feature: 'rainfall_1hr_in',      value: rainfall,  weight: +(rainfall / total).toFixed(2) },
    { feature: 'soil_moisture_index',  value: soil,      weight: +(soil / total).toFixed(2) },
  ];
}

function RouteCard({ route, index, isDemo }) {
  if (!route) return null;
  const props = route.properties || {};
  const routeColors = ['#22c55e', '#3b82f6', '#a855f7'];
  const routeNames  = ['Primary Route', 'Alternate Route 1', 'Alternate Route 2'];
  const routeLabels = ['FASTEST', 'ALT 1', 'ALT 2'];
  const hp = props.max_hazard_penalty || 0;
  const triggered = props.pre_emptive_trigger;
  const bgColor = triggered ? 'rgba(127,29,29,0.3)' : 'rgba(30,51,83,0.5)';
  const borderColor = triggered ? '#ef4444' : routeColors[index];

  return (
    <div style={{
      background: bgColor,
      border: `1px solid ${borderColor}`,
      borderRadius: 8,
      padding: '10px 12px',
      marginBottom: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: triggered ? '#ef4444' : routeColors[index], flexShrink: 0 }} />
        <span style={{ fontWeight: 600, fontSize: 13 }}>{routeNames[index]}</span>
        <span className={`badge ${triggered ? 'badge-red' : 'badge-blue'}`} style={{ marginLeft: 'auto', fontSize: 10 }}>
          {triggered ? '⚠️ REROUTED' : routeLabels[index]}
        </span>
      </div>
      {triggered && props.alert_message && (
        <div style={{ fontSize: 11, color: '#fca5a5', background: 'rgba(239,68,68,0.1)', borderRadius: 4, padding: '4px 8px', marginBottom: 6 }}>
          {props.alert_message}
        </div>
      )}
      <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
        <div>
          <span style={{ color: '#64748b' }}>ETA </span>
          <span style={{ fontWeight: 600 }}>{props.eta_minutes || '--'} min</span>
        </div>
        <div>
          <span style={{ color: '#64748b' }}>Risk </span>
          <span style={{ fontWeight: 600, color: hp >= 0.65 ? '#ef4444' : hp >= 0.35 ? '#f97316' : '#22c55e' }}>
            {(hp * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

// Fallback-mode route card — backend returned {status:"fallback", primary,
// alternate1, alternate2} instead of GeoJSON features (Fix 5). Each route
// object has corridor/hazard_score/eta_minutes/segments/shelter/hospital/fuel.
function FallbackRouteCard({ route, index }) {
  if (!route) return null;
  const routeColors = ['#22c55e', '#3b82f6', '#a855f7'];
  const routeNames  = ['Primary Route', 'Alternate Route 1', 'Alternate Route 2'];
  const routeLabels = ['FASTEST', 'ALT 1', 'ALT 2'];
  const hp = route.hazard_score || 0;

  return (
    <div style={{
      background: 'rgba(30,51,83,0.5)',
      border: `1px solid ${routeColors[index]}`,
      borderRadius: 8,
      padding: '10px 12px',
      marginBottom: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: routeColors[index], flexShrink: 0 }} />
        <span style={{ fontWeight: 600, fontSize: 13 }}>{routeNames[index]}</span>
        <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 4 }}>{route.corridor}</span>
        <span className="badge badge-blue" style={{ marginLeft: 'auto', fontSize: 10 }}>
          {routeLabels[index]}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 16, fontSize: 12, marginBottom: 6 }}>
        <div>
          <span style={{ color: '#64748b' }}>ETA </span>
          <span style={{ fontWeight: 600 }}>{route.eta_minutes ?? '--'} min</span>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
            <span style={{ color: '#64748b' }}>Hazard Score</span>
            <span style={{ color: hp >= 0.65 ? '#ef4444' : hp >= 0.35 ? '#f97316' : '#22c55e', fontWeight: 600 }}>{(hp * 100).toFixed(0)}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${hp * 100}%`, background: hp >= 0.65 ? '#ef4444' : hp >= 0.35 ? '#f97316' : '#22c55e' }} />
          </div>
        </div>
      </div>
      <div style={{ fontSize: 11, color: '#94a3b8' }}>
        🏠 {route.shelter || '--'} · 🏥 {route.hospital || '--'} · ⛽ {route.fuel || '--'}
      </div>
    </div>
  );
}

export default function Sidebar({
  tier, onTierChange, mhrm, hazards, routes, economic, facilities,
  demoState, lastUpdated, isConnected, mobile = false,
  regionPill = 'CA', onActivateZone, health,
}) {
  const [activeTab, setActiveTab] = useState('hazards');
  const isFallback    = routes?.status === 'fallback';
  const routeFeatures = !isFallback ? (routes?.features || []) : [];
  const fallbackRoutes = isFallback
    ? [routes.primary, routes.alternate1, routes.alternate2].filter(Boolean)
    : [];
  const mhrmFeatures  = mhrm?.features   || [];

  const shelterList = facilities?.shelters?.length || facilities?.hospitals?.length
    ? [
        ...(facilities.shelters || []).map(s => ({ ...s, type: 'Shelter' })),
        ...(facilities.hospitals || []).map(h => ({ ...h, type: 'Hospital' })),
      ]
    : FALLBACK_SHELTERS;

  const outerStyle = mobile
    ? { display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' }
    : { width: 320, height: '100%', background: '#0d1b2a', borderLeft: '1px solid #1e3a5c', display: 'flex', flexDirection: 'column', overflow: 'hidden' };

  // T1 plain-language summary derived from primary route / demo state
  const primaryRoute = isFallback ? routes.primary : routeFeatures[0];
  const primaryProps = isFallback ? primaryRoute : primaryRoute?.properties;
  const primaryDominantHazard = primaryProps?.dominant_hazard
    ? dominantHazardLabel(primaryProps.dominant_hazard) : null;
  const avoidedSegment = primaryProps?.segments?.[0] || demoState?.segment || 'an affected segment';
  const hazardTypeWord = primaryProps?.dominant_hazard || 'hazard';

  const health1 = health?.data_sources || {};
  const healthRow = [
    { key: 'usgs_nwis', label: 'USGS' },
    { key: 'noaa',      label: 'NOAA' },
    { key: 'firms',     label: 'FIRMS' },
    { key: 'usgs_eq',   label: 'USGS-EQ' },
  ].map(s => ({ ...s, ok: !!health1[s.key]?.available }));

  return (
    <div style={outerStyle}>
      {/* Header */}
      <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid #1e3a5c', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: isConnected ? '#22c55e' : '#ef4444',
          }} className={isConnected ? '' : 'blink'} />
          <span style={{ fontSize: 11, color: '#64748b' }}>
            {isConnected ? `LIVE · ${lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : '--'}` : 'RECONNECTING…'}
          </span>
          {demoState?.active && (
            <span className="badge badge-brown pulse-brown" style={{ marginLeft: 'auto' }}>DEMO</span>
          )}
        </div>
        {/* Tier selector */}
        <div style={{ display: 'flex', gap: 4 }}>
          {TIER_LABELS.map((label, i) => (
            <button
              key={i}
              onClick={() => onTierChange(i + 1)}
              title={TIER_INFO[i].full}
              style={{
                flex: 1,
                padding: '5px 4px',
                minHeight: 44,
                fontSize: 11,
                fontWeight: tier === i + 1 ? 700 : 400,
                background: tier === i + 1 ? '#1e4080' : '#1a2942',
                border: `1px solid ${tier === i + 1 ? '#3b82f6' : '#2d4a6e'}`,
                borderRadius: 6,
                color: tier === i + 1 ? '#60a5fa' : '#94a3b8',
                cursor: 'pointer',
                letterSpacing: '0.02em',
              }}
            >
              T{i + 1} · {label}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 5 }}>
          {TIER_INFO[tier - 1]?.short}
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>

        {isFallback && (
          <div style={{ background: 'rgba(234,179,8,0.15)', border: '1px solid #eab308', color: '#fbbf24', borderRadius: 6, padding: '6px 10px', fontSize: 11, marginBottom: 10 }}>
            ⚠️ Showing pre-computed corridors — live graph unavailable
          </div>
        )}

        {/* ── TIER 1: DRIVER ── */}
        {tier === 1 && (
          <div>
            <div className="card">
              <div className="card-title">🗺 Route Summary</div>
              {demoState?.active ? (
                <div style={{ fontSize: 13, color: '#fca5a5', background: 'rgba(239,68,68,0.1)', borderRadius: 6, padding: '8px 10px' }}>
                  TAKE {demoState.reroute?.corridor || '--'} — Flood risk detected ahead on {demoState.segment || 'segment'} ·
                  {' '}P(flood)={demoState.flood_prob !== undefined ? Math.round(demoState.flood_prob * 100) : '--'}% exceeds safety threshold
                </div>
              ) : isFallback ? (
                <FallbackRouteCard route={routes.primary} index={0} />
              ) : routeFeatures.length > 0 ? (
                <RouteCard route={routeFeatures[0]} index={0} isDemo={demoState?.active} />
              ) : (
                <div style={{ color: '#64748b', textAlign: 'center', padding: 12 }}>
                  Enter origin & destination to compute route
                </div>
              )}
              {primaryRoute && !demoState?.active && (
                <div style={{ marginTop: 8, fontSize: 12, color: '#cbd5e1' }}>
                  Take {primaryProps?.corridor || (isFallback ? routes.primary?.corridor : 'this route')} — {hazardTypeWord} risk ahead on {avoidedSegment}.
                  {primaryDominantHazard && <span style={{ color: '#94a3b8' }}> ({primaryDominantHazard})</span>}
                  <div style={{ marginTop: 4, color: '#94a3b8' }}>
                    🏠 Nearest shelter: {primaryProps?.shelter || '--'} · 🏥 Nearest hospital: {primaryProps?.hospital || '--'}
                  </div>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-title">🚦 Road Conditions</div>
              {hazards ? (
                <div style={{ fontSize: 13 }}>
                  {hazards.compound?.critical_segments > 0 ? (
                    <div style={{ color: '#fca5a5', padding: '8px 10px', background: 'rgba(239,68,68,0.1)', borderRadius: 6 }}>
                      ⚠️ {hazards.compound.critical_segments} road segment(s) currently at high risk. Consider alternate routes.
                    </div>
                  ) : (
                    <div style={{ color: '#86efac', padding: '8px 10px', background: 'rgba(34,197,94,0.1)', borderRadius: 6 }}>
                      ✅ Road conditions are currently safe. No critical hazards detected.
                    </div>
                  )}
                </div>
              ) : <div style={{ color: '#64748b' }}>Loading…</div>}
            </div>

            <div className="card">
              <div className="card-title">📍 ETA to Safety</div>
              {isFallback && routes.primary ? (
                <div style={{ fontSize: 22, fontWeight: 700, color: '#22c55e' }}>
                  {routes.primary.eta_minutes ?? '--'} min
                  <div style={{ fontSize: 12, fontWeight: 400, color: '#64748b', marginTop: 2 }}>
                    via {routes.primary.corridor || 'primary corridor'}
                  </div>
                </div>
              ) : routeFeatures[0] ? (
                <div style={{ fontSize: 22, fontWeight: 700, color: '#22c55e' }}>
                  {routeFeatures[0].properties?.eta_minutes || '--'} min
                  <div style={{ fontSize: 12, fontWeight: 400, color: '#64748b', marginTop: 2 }}>
                    via {routeFeatures[0].properties?.route_type === 'primary' ? 'primary route' : 'alternate route'}
                  </div>
                </div>
              ) : (
                <div style={{ color: '#64748b', fontSize: 13 }}>Set a destination to see ETA</div>
              )}
            </div>
          </div>
        )}

        {/* ── TIER 2: FIRST RESPONDER ── */}
        {tier === 2 && (
          <div>
            {demoState?.active && (
              <div className="card">
                <div className="card-title">🎬 Demo: Active Reroute</div>
                <div style={{ fontSize: 12, color: '#fca5a5', marginBottom: 8 }}>
                  Avoiding {demoState.segment || 'segment'} — P(flood)={demoState.flood_prob !== undefined ? Math.round(demoState.flood_prob * 100) : '--'}%
                </div>
                {fallbackRoutes.length > 0
                  ? fallbackRoutes.map((r, i) => <FallbackRouteCard key={i} route={r} index={i} />)
                  : <div style={{ color: '#64748b', fontSize: 12 }}>Awaiting reroute corridor data…</div>}
              </div>
            )}

            <div className="card">
              <div className="card-title">🚨 All Routes ({isFallback ? fallbackRoutes.length : routeFeatures.length})</div>
              {isFallback ? (
                fallbackRoutes.length > 0
                  ? fallbackRoutes.map((r, i) => <FallbackRouteCard key={i} route={r} index={i} />)
                  : <div style={{ color: '#64748b', textAlign: 'center', padding: 12 }}>No corridor data available</div>
              ) : routeFeatures.length > 0 ? (
                routeFeatures.map((r, i) => (
                  <RouteCard key={i} route={r} index={i} isDemo={demoState?.active} />
                ))
              ) : (
                <div style={{ color: '#64748b', textAlign: 'center', padding: 12 }}>
                  Set origin & destination to compute routes
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-title">🏥 Shelter &amp; Hospital Locations</div>
              {shelterList.map((s, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 0',
                  borderBottom: i < shelterList.length - 1 ? '1px solid #1e3353' : 'none',
                  fontSize: 12,
                }}>
                  <span style={{ fontSize: 16 }}>{s.type === 'Hospital' ? '🏥' : '🏠'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    <div style={{ color: '#64748b', fontSize: 11 }}>
                      {s.type === 'Hospital'
                        ? (s.beds ? `${s.beds} beds` : `${s.lat?.toFixed?.(4)}, ${s.lng?.toFixed?.(4)}`)
                        : (s.capacity ? `Cap: ${s.capacity?.toLocaleString()}` : `${s.lat?.toFixed?.(4)}, ${s.lng?.toFixed?.(4)}`)}
                    </div>
                  </div>
                  <span className={`badge ${s.type === 'Hospital' ? 'badge-blue' : 'badge-green'}`}>
                    {s.type}
                  </span>
                </div>
              ))}
            </div>

            {hazards && (
              <div className="card">
                <div className="card-title">⚡ Hazard Scores</div>
                <HazardBar label="Max Flood Prob" value={hazards.flood?.max_probability || 0} color="#3b82f6" />
                <HazardBar label="Wildfire Zone Score" value={hazards.wildfire?.zone_a_segments > 0 ? 1.0 : hazards.wildfire?.zone_b_segments > 0 ? 0.6 : 0.2} color="#f97316" />
                <HazardBar label="Seismic Shaking" value={hazards.seismic?.max_pga_g * 2 || 0} color="#a855f7" />
                <HazardBar label="Compound Risk" value={hazards.compound?.max_hazard_penalty || 0} color="#ef4444" />
              </div>
            )}

            {/* Zone status + zone-override demo buttons (Fix 9/12, T2 only) */}
            {hazards?.wildfire && (
              <div className="card">
                <div className="card-title">🔥 Wildfire Zone Status</div>
                <div style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.6 }}>
                  <div>Zone A (0–2 mi): {hazards.wildfire.zone_a_segments ?? 0} segments affected</div>
                  <div>Zone B (2–10 mi): {hazards.wildfire.zone_b_segments ?? 0} segments affected</div>
                  <div>Zone C (10–25 mi): {hazards.wildfire.zone_c_segments ?? 0} segments affected</div>
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                  <button onClick={() => onActivateZone?.('a')} className="btn btn-secondary" style={{ flex: 1, fontSize: 11, minHeight: 36, justifyContent: 'center' }}>Activate Zone A</button>
                  <button onClick={() => onActivateZone?.('b')} className="btn btn-secondary" style={{ flex: 1, fontSize: 11, minHeight: 36, justifyContent: 'center' }}>Activate Zone B</button>
                  <button onClick={() => onActivateZone?.('clear')} className="btn btn-secondary" style={{ flex: 1, fontSize: 11, minHeight: 36, justifyContent: 'center' }}>Clear Zones</button>
                </div>
              </div>
            )}

            {/* SHAP breakdown for demo or hazard alerts with shap_top_features (T2/T3) */}
            {demoState?.active && (
              <div className="card">
                <SHAPBreakdown features={demoState.shap_top_features || synthesizeDemoSHAP(demoState)} approximation />
              </div>
            )}
          </div>
        )}

        {/* ── TIER 3: EMERGENCY MANAGER ── */}
        {tier === 3 && (
          <div>
            {/* Tab switcher */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
              {['hazards', 'mhrm', 'economic'].map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    flex: 1,
                    padding: '5px 4px',
                    minHeight: 40,
                    fontSize: 11,
                    fontWeight: activeTab === tab ? 700 : 400,
                    background: activeTab === tab ? '#1e4080' : '#1a2942',
                    border: `1px solid ${activeTab === tab ? '#3b82f6' : '#2d4a6e'}`,
                    borderRadius: 6,
                    color: activeTab === tab ? '#60a5fa' : '#94a3b8',
                    cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}
                >
                  {tab === 'mhrm' ? 'MHRM' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {demoState?.active && (
              <div className="card">
                <div className="card-title">🎬 Demo Detail</div>
                <div style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.7 }}>
                  <div>P(flood): {demoState.flood_prob !== undefined ? `${Math.round(demoState.flood_prob * 100)}%` : '--'}</div>
                  <div>Edge weight: {demoState.edge_weight ?? 9.5}</div>
                  <div>Trigger time: {demoState.trigger_time_display || '--'}</div>
                  {demoState.patent_note && (
                    <div style={{ marginTop: 6, color: '#94a3b8', fontStyle: 'italic' }}>{demoState.patent_note}</div>
                  )}
                </div>
                <SHAPBreakdown features={demoState.shap_top_features || synthesizeDemoSHAP(demoState)} approximation />
              </div>
            )}

            {!isFallback && routeFeatures.length > 0 && (
              <div className="card">
                <div className="card-title">🔁 Route Independence</div>
                {routeFeatures.map((r, i) => (
                  <div key={i} style={{ fontSize: 11, color: r.properties?.independent_of_primary ? '#86efac' : '#fca5a5', marginBottom: 3 }}>
                    {r.properties?.route_type || `Route ${i+1}`}: {r.properties?.independent_of_primary ? '✓ Routes independently verified — no shared segments' : '⚠️ Shares segments with primary'}
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'hazards' && hazards && (
              <div>
                {/* Flood */}
                <div className="card">
                  <div className="card-title" style={{ color: '#60a5fa' }}>🌊 Flood</div>
                  <div style={{ fontSize: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                    {[
                      { k: 'Max Prob', v: `${((hazards.flood?.max_probability || 0) * 100).toFixed(1)}%` },
                      { k: 'High-Risk Segs', v: hazards.flood?.high_risk_segments },
                      { k: 'Active Gauges', v: hazards.flood?.active_gauges },
                      { k: 'Source', v: hazards.flood?.is_live ? '🟢 Live' : '🟡 Synthetic' },
                    ].map(({ k, v }) => (
                      <div key={k}>
                        <div style={{ color: '#64748b', fontSize: 11 }}>{k}</div>
                        <div style={{ fontWeight: 600 }}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Wildfire */}
                <div className="card">
                  <div className="card-title" style={{ color: '#fb923c' }}>🔥 Wildfire</div>
                  <div style={{ fontSize: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                    {[
                      { k: 'Zone A Segs', v: hazards.wildfire?.zone_a_segments },
                      { k: 'Zone B Segs', v: hazards.wildfire?.zone_b_segments },
                      { k: 'Zone C Segs', v: hazards.wildfire?.zone_c_segments },
                      { k: 'Fire Detections', v: hazards.wildfire?.active_fire_detections },
                      { k: 'Source', v: hazards.wildfire?.is_live ? '🟢 NASA FIRMS' : '🟡 Synthetic' },
                    ].map(({ k, v }) => (
                      <div key={k}>
                        <div style={{ color: '#64748b', fontSize: 11 }}>{k}</div>
                        <div style={{ fontWeight: 600 }}>{v ?? '--'}</div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Seismic */}
                <div className="card">
                  <div className="card-title" style={{ color: '#c084fc' }}>🌍 Seismic</div>
                  <div style={{ fontSize: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                    {[
                      { k: 'Max PGA (g)', v: hazards.seismic?.max_pga_g?.toFixed(4) },
                      { k: 'Recent EQs', v: hazards.seismic?.recent_earthquakes },
                      { k: 'Significant (M4+)', v: hazards.seismic?.significant_eqs },
                      { k: 'Bridges at Risk', v: hazards.seismic?.bridges_at_risk },
                      { k: 'Source', v: hazards.seismic?.is_live ? '🟢 USGS Live' : '🟡 Synthetic' },
                    ].map(({ k, v }) => (
                      <div key={k}>
                        <div style={{ color: '#64748b', fontSize: 11 }}>{k}</div>
                        <div style={{ fontWeight: 600 }}>{v ?? '--'}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'mhrm' && (
              <div>
                <div className="card">
                  <div className="card-title">🗺 Per-Segment Compound Risk ({mhrmFeatures.length} segments)</div>
                  <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6 }}>
                    Combined score per road segment — worst of flood, wildfire &amp; seismic risk below it
                  </div>
                  <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                    {[...mhrmFeatures]
                      .sort((a, b) => b.properties.hazard_penalty - a.properties.hazard_penalty)
                      .map(feat => {
                        const p = feat.properties;
                        const hp = p.hazard_penalty;
                        const color = hp >= 0.65 ? '#ef4444' : hp >= 0.35 ? '#f97316' : hp >= 0.15 ? '#eab308' : '#22c55e';
                        const dhLabel = dominantHazardLabel(p.dominant_hazard);
                        const stageArrow = p.stage_rate_ft_hr > 0.05 ? ' ↑ Rising' : p.stage_rate_ft_hr < -0.05 ? ' ↓ Falling' : ' → Stable';
                        const hasHorizons = p.flood_prob_30 !== undefined || p.flood_prob_60 !== undefined || p.flood_prob_90 !== undefined;
                        return (
                          <div key={p.id} style={{
                            padding: '7px 0',
                            borderBottom: '1px solid #1a2942',
                            fontSize: 11,
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                              <span style={{ fontWeight: 500 }}>{p.name}</span>
                              <span
                                title={HAZARD_PENALTY_TOOLTIP}
                                style={{ color, fontWeight: 700, cursor: 'help' }}
                              >
                                {(hp * 100).toFixed(0)}% {dhLabel ? `· ${dhLabel}` : ''} ⓘ
                              </span>
                            </div>
                            <div style={{ color: '#64748b', fontSize: 10 }}>
                              Flood: {(p.flood_probability * 100).toFixed(0)}%{stageArrow} ·
                              WF: {p.wildfire_zone !== 'none' ? `Zone ${p.wildfire_zone}` : 'Clear'} ·
                              PGA: {p.seismic_pga_g}g
                            </div>
                            {hasHorizons && (
                              <div style={{ color: '#60a5fa', fontSize: 10, marginTop: 2 }}>
                                P(flood) t+30: {((p.flood_prob_30||0)*100).toFixed(0)}% · t+60: {((p.flood_prob_60||0)*100).toFixed(0)}% · t+90: {((p.flood_prob_90||0)*100).toFixed(0)}%
                              </div>
                            )}
                            {p.shap_top_features?.length > 0 && (
                              <SHAPBreakdown features={p.shap_top_features} />
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'economic' && (
              <EconomicDashboard economic={economic} />
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '8px 14px',
        borderTop: '1px solid #1e3a5c',
        fontSize: 10,
        color: '#475569',
        flexShrink: 0,
      }}>
        <div>UDIARS v1.0 POC · CA · NY · NJ · Data auto-refreshes every 60s</div>
        {mobile ? (
          <div style={{ marginTop: 4 }}>
            Sources: USGS {healthRow.find(h => h.key === 'usgs_nwis')?.ok ? '✓' : '✗'} ·
            {' '}NOAA {healthRow.find(h => h.key === 'noaa')?.ok ? '✓' : '✗'} ·
            {' '}FIRMS {healthRow.find(h => h.key === 'firms')?.ok ? '✓' : '✗'} ·
            {' '}EQ {healthRow.find(h => h.key === 'usgs_eq')?.ok ? '✓' : '✗'}
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 10, marginTop: 4, flexWrap: 'wrap' }}>
            {healthRow.map(s => (
              <span key={s.key} style={{ color: s.ok ? '#86efac' : '#f87171' }}>
                {s.label} {s.ok ? '✓' : '✗'}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
