/**
 * ControlPanel — origin/destination geocoder, hazard toggles, demo controls.
 */
import React, { useState, useEffect } from 'react';
import { PRESET_GROUPS } from '../constants/appData';

async function geocodeAddress(query) {
  if (!query || query.trim().length < 3) return null;
  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error('Geocoding service unavailable');
  const data = await res.json();
  if (!data?.length) return null;
  return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon), display: data[0].display_name };
}

export default function ControlPanel({
  mobile = false,
  onRouteCompute,
  onDemoStart,
  onDemoStop,
  onForceRefresh,
  onHazardToggle,
  demoState,
  hazardVisibility,
  isConnected,
  lastUpdated,
  region,
  onRegionChange,
  regionPill = 'CA',
  onRegionPillChange,
  subFocus = 'BOTH',
  onSubFocusChange,
  isMobile = false,
  onOpenHelp,
  onOpenTips,
  onOpenReadMe,
}) {
  const [originLat,  setOriginLat]  = useState('34.0560');
  const [originLng,  setOriginLng]  = useState('-118.2356');
  const [destLat,    setDestLat]    = useState('34.0195');
  const [destLng,    setDestLng]    = useState('-118.4912');
  const [originAddr, setOriginAddr] = useState('');
  const [destAddr,   setDestAddr]   = useState('');
  const [geoStatus,  setGeoStatus]  = useState({ origin: '', dest: '' });
  const [computing,  setComputing]  = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const [presetMode, setPresetMode]  = useState('origin');

  const handleCompute = async () => {
    setComputing(true);
    try {
      await onRouteCompute(
        parseFloat(originLat), parseFloat(originLng),
        parseFloat(destLat),   parseFloat(destLng),
        regionPill
      );
    } finally {
      setComputing(false);
    }
  };

  // Demo button label/handler vary by active region pill (Fix 3 sub-item 5)
  const DEMO_CONFIG = {
    CA:   { label: '🎬 Demo: US-101 Flood (Ventura→SLO)' },
    NJNY: { label: '🎬 Demo: Raritan Flood (New Brunswick NJ)' },
    ALL:  { label: '🎬 Demo: Multi-State Flood Event' },
  };
  const demoCfg = DEMO_CONFIG[regionPill] || DEMO_CONFIG.CA;
  const handleDemoStart = () => onDemoStart(regionPill);

  // Live countdown for demo auto-reset (Fix 6) — belt-and-suspenders UI
  // feedback only; the backend is the source of truth and auto-resets
  // server-side after 60s regardless of this client-side timer.
  const [secondsLeft, setSecondsLeft] = useState(null);
  useEffect(() => {
    if (!demoState?.active) { setSecondsLeft(null); return; }
    setSecondsLeft(demoState.reset_in_seconds ?? 58);
    const interval = setInterval(() => {
      setSecondsLeft(s => {
        if (s === null) return null;
        if (s <= 1) {
          clearInterval(interval);
          onDemoStop?.();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoState?.active, demoState?.reset_in_seconds]);

  // Offline confidence indicator (Fix 9) — ticks every 5s since it's time-based.
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(interval);
  }, []);
  const secondsSinceRefresh = lastUpdated ? (now - new Date(lastUpdated).getTime()) / 1000 : null;
  const confidence = secondsSinceRefresh === null ? null
    : secondsSinceRefresh > 180 ? 'LOW'
    : secondsSinceRefresh > 90  ? 'MED'
    : 'HIGH';

  const handleGeocode = async (which) => {
    const query = which === 'origin' ? originAddr : destAddr;
    setGeoStatus(s => ({ ...s, [which]: 'Searching…' }));
    try {
      const result = await geocodeAddress(query);
      if (!result) {
        setGeoStatus(s => ({ ...s, [which]: 'No match found' }));
        return;
      }
      if (which === 'origin') {
        setOriginLat(result.lat.toFixed(6));
        setOriginLng(result.lng.toFixed(6));
      } else {
        setDestLat(result.lat.toFixed(6));
        setDestLng(result.lng.toFixed(6));
      }
      setGeoStatus(s => ({ ...s, [which]: '✓ Found' }));
    } catch (err) {
      setGeoStatus(s => ({ ...s, [which]: 'Lookup failed' }));
    }
  };

  // Clicking the same mode again toggles the list closed; switching mode keeps it open.
  const togglePresetMode = (mode) => {
    if (presetMode === mode && showPresets) {
      setShowPresets(false);
    } else {
      setPresetMode(mode);
      setShowPresets(true);
    }
  };

  const applyPreset = (preset) => {
    if (presetMode === 'origin') {
      setOriginLat(preset.lat.toString());
      setOriginLng(preset.lng.toString());
    } else {
      setDestLat(preset.lat.toString());
      setDestLng(preset.lng.toString());
    }
    setShowPresets(false);
  };

  // Filter preset groups by active region pill (Fix 4): CA shows LA+SF groups,
  // NJNY shows NY+NJ groups, ALL shows everything grouped by state label.
  const visiblePresetGroups = PRESET_GROUPS.filter(group => {
    if (regionPill === 'ALL') return true;
    if (regionPill === 'CA') return group.region === 'CA';
    if (regionPill === 'NJNY') return group.region === 'NY' || group.region === 'NJ';
    return true;
  });

  const inputStyle = {
    background: '#1a2942',
    border: '1px solid #2d4a6e',
    borderRadius: 5,
    color: '#e2e8f0',
    padding: '5px 8px',
    fontSize: 12,
    width: '100%',
    outline: 'none',
  };

  const labelStyle = { fontSize: 11, color: '#64748b', marginBottom: 3, display: 'block' };

  const wrapStyle = mobile
    ? { padding: '4px 0 8px' }
    : {
        position: 'absolute', top: 14, left: 14, zIndex: 1000,
        width: 290, background: 'rgba(13,27,42,0.95)',
        border: '1px solid #1e3a5c', borderRadius: 10,
        padding: '14px 14px 10px', backdropFilter: 'blur(8px)',
        maxHeight: 'calc(100vh - 28px)', overflowY: 'auto',
      };

  return (
    <div style={wrapStyle}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: '0.02em' }}>
            🛡 UDIARS
          </div>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#94a3b8', marginTop: 1 }}>
            UNIFIED DISASTER INTELLIGENCE AND ADAPTIVE RESPONSE SYSTEM
          </div>
          <div style={{ fontSize: 10, color: '#475569', marginTop: 1 }}>
            POC Regions: California &middot; New Jersey / New York
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: isConnected ? '#22c55e' : '#ef4444',
          }} />
          <span style={{ fontSize: 10, color: '#64748b' }}>
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Region pills (Fix 3) — replaces the old single StateSelector dropdown */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
        {[
          { id: 'CA',   label: 'California' },
          { id: 'NJNY', label: 'New Jersey / New York' },
          { id: 'ALL',  label: 'All Regions' },
        ].map(p => {
          const active = regionPill === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onRegionPillChange?.(p.id)}
              className="btn btn-secondary"
              style={{
                flex: 1, fontSize: 11, padding: '6px 6px', minHeight: 32,
                justifyContent: 'center',
                background: active ? '#1e4080' : '#1a2942',
                border: `1px solid ${active ? '#3b82f6' : '#2d4a6e'}`,
                color: active ? '#60a5fa' : '#94a3b8',
                fontWeight: active ? 700 : 400,
              }}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      {/* Sub-state focus — desktop only, only shown when NJNY pill is active */}
      {!isMobile && regionPill === 'NJNY' && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
          {[
            { id: 'NJ',   label: 'Focus: New Jersey' },
            { id: 'NY',   label: 'Focus: New York' },
            { id: 'BOTH', label: 'Show Both' },
          ].map(f => {
            const active = subFocus === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => onSubFocusChange?.(f.id)}
                className="btn btn-secondary"
                style={{
                  flex: 1, fontSize: 10, padding: '4px 4px', minHeight: 28,
                  justifyContent: 'center',
                  background: active ? '#1e4080' : '#1a2942',
                  border: `1px solid ${active ? '#3b82f6' : '#2d4a6e'}`,
                  color: active ? '#60a5fa' : '#94a3b8',
                  fontWeight: active ? 700 : 400,
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Info buttons */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 10, alignItems: 'center' }}>
        <div style={{ flex: 1 }} />
        <button onClick={onOpenHelp} className="btn btn-secondary" title="Emergency hotlines" style={{ fontSize: 11, padding: '4px 8px', minHeight: 32 }}>📞 Help</button>
        <button onClick={onOpenTips} className="btn btn-secondary" title="Emergency tips" style={{ fontSize: 11, padding: '4px 8px', minHeight: 32 }}>🧭 Tips</button>
        <button onClick={onOpenReadMe} className="btn btn-secondary" title="How this app works" style={{ fontSize: 11, padding: '4px 8px', minHeight: 32 }}>📖</button>
      </div>

      {/* Routing inputs */}
      <div style={{ marginBottom: 10 }}>
        {/* Address search */}
        <div style={{ marginBottom: 6 }}>
          <label style={labelStyle}>Origin Address (search)</label>
          <div style={{ display: 'flex', gap: 4 }}>
            <input value={originAddr} onChange={e => setOriginAddr(e.target.value)} style={inputStyle} placeholder="e.g. 123 Main St, Los Angeles, CA"
              onKeyDown={e => { if (e.key === 'Enter') handleGeocode('origin'); }} />
            <button onClick={() => handleGeocode('origin')} className="btn btn-secondary" style={{ fontSize: 11, padding: '5px 8px' }}>🔍</button>
          </div>
          {geoStatus.origin && <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>{geoStatus.origin}</div>}
        </div>
        <div style={{ marginBottom: 8 }}>
          <label style={labelStyle}>Destination Address (search)</label>
          <div style={{ display: 'flex', gap: 4 }}>
            <input value={destAddr} onChange={e => setDestAddr(e.target.value)} style={inputStyle} placeholder="e.g. LAX Airport"
              onKeyDown={e => { if (e.key === 'Enter') handleGeocode('dest'); }} />
            <button onClick={() => handleGeocode('dest')} className="btn btn-secondary" style={{ fontSize: 11, padding: '5px 8px' }}>🔍</button>
          </div>
          {geoStatus.dest && <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>{geoStatus.dest}</div>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 6 }}>
          <div>
            <label style={labelStyle}>Origin Lat</label>
            <input value={originLat} onChange={e => setOriginLat(e.target.value)} style={inputStyle} placeholder="34.0560" />
          </div>
          <div>
            <label style={labelStyle}>Origin Lng</label>
            <input value={originLng} onChange={e => setOriginLng(e.target.value)} style={inputStyle} placeholder="-118.2356" />
          </div>
          <div>
            <label style={labelStyle}>Dest Lat</label>
            <input value={destLat} onChange={e => setDestLat(e.target.value)} style={inputStyle} placeholder="34.0195" />
          </div>
          <div>
            <label style={labelStyle}>Dest Lng</label>
            <input value={destLng} onChange={e => setDestLng(e.target.value)} style={inputStyle} placeholder="-118.4912" />
          </div>
        </div>

        {/* Preset picker */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
          {['origin', 'dest'].map(mode => (
            <button
              key={mode}
              type="button"
              onClick={() => togglePresetMode(mode)}
              className="btn btn-secondary"
              style={{
                flex: 1, fontSize: 11, minHeight: 32,
                outline: presetMode === mode && showPresets ? '1px solid #3b82f6' : 'none',
              }}
            >
              📍 {mode === 'origin' ? 'Origin' : 'Dest'} Presets
            </button>
          ))}
        </div>

        {showPresets && (
          <div style={{
            background: '#1a2942',
            border: '1px solid #2d4a6e',
            borderRadius: 6,
            padding: 8,
            marginBottom: 6,
          }}>
            <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6 }}>
              SET {presetMode.toUpperCase()} →
            </div>
            {visiblePresetGroups.map(group => (
              <div key={group.label} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: '#3b82f6', marginBottom: 4 }}>{group.label} ({group.region})</div>
                {group.items.map(p => (
                  <button key={p.label} type="button" onClick={() => applyPreset(p)}
                    style={{ display: 'block', width: '100%', textAlign: 'left', background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 11, padding: '6px 0', minHeight: 28, cursor: 'pointer' }}>
                    → {p.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}

        <button
          onClick={handleCompute}
          disabled={computing}
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', fontSize: 13 }}
        >
          {computing ? '⏳ Computing…' : '🗺 Compute Routes'}
        </button>
      </div>

      {/* Hazard layer toggles */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Hazard Overlays
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {[
            { key: 'flood',    label: '🌊 Flood',    color: '#3b82f6' },
            { key: 'wildfire', label: '🔥 Wildfire', color: '#f97316' },
            { key: 'seismic',  label: '🌍 Seismic',  color: '#a855f7' },
            { key: 'mhrm',     label: '⚡ MHRM',     color: '#ef4444' },
          ].map(layer => (
            <button
              key={layer.key}
              onClick={() => onHazardToggle(layer.key)}
              style={{
                padding: '4px 10px',
                minHeight: 32,
                borderRadius: 5,
                border: `1px solid ${hazardVisibility[layer.key] ? layer.color : '#2d4a6e'}`,
                background: hazardVisibility[layer.key] ? `${layer.color}22` : '#1a2942',
                color: hazardVisibility[layer.key] ? layer.color : '#64748b',
                fontSize: 11,
                cursor: 'pointer',
                fontWeight: hazardVisibility[layer.key] ? 600 : 400,
              }}
            >
              {layer.label}
            </button>
          ))}
        </div>
      </div>

      {/* Demo mode */}
      <div style={{ borderTop: '1px solid #1e3a5c', paddingTop: 8 }}>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          {!demoState?.active ? (
            <button
              onClick={handleDemoStart}
              className="btn btn-danger"
              style={{ flex: 1, justifyContent: 'center', fontSize: 12, minHeight: 36 }}
            >
              {demoCfg.label}
            </button>
          ) : (
            <button
              onClick={onDemoStop}
              className="btn btn-success"
              style={{ flex: 1, justifyContent: 'center', fontSize: 12, minHeight: 36 }}
            >
              ✅ Stop Demo
            </button>
          )}
          <button
            onClick={() => onForceRefresh(regionPill)}
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '6px 10px', minHeight: 36, minWidth: 44 }}
            title="Force data refresh"
          >
            🔄
          </button>
        </div>
        {demoState?.active && (
          <div style={{ marginTop: 6, fontSize: 11, color: '#fca5a5', padding: '5px 8px', background: 'rgba(127,29,29,0.3)', borderRadius: 5 }}>
            🟤 Demo active — auto-reset in {secondsLeft ?? '--'}s
          </div>
        )}
        {lastUpdated && (
          <div style={{ marginTop: 6, fontSize: 10, color: '#475569', textAlign: 'center' }}>
            Last refresh: {new Date(lastUpdated).toLocaleTimeString()}
          </div>
        )}
        {confidence && confidence !== 'HIGH' && (
          <div style={{ marginTop: 4, fontSize: 10, color: confidence === 'LOW' ? '#f87171' : '#fbbf24', textAlign: 'center' }}>
            ⚠️ Data stale — last update {Math.round(secondsSinceRefresh)}s ago · Confidence: {confidence}
          </div>
        )}
      </div>
    </div>
  );
}
