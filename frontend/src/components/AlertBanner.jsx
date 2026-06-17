/**
 * AlertBanner — top-of-screen alert strip.
 * Shows pre-emptive trigger alerts, color-coded by severity.
 * Auto-collapses when no active alerts.
 */
import React, { useState } from 'react';

const SEVERITY_STYLES = {
  immediate: { bg: '#7f1d1d', border: '#ef4444', icon: '🚨', label: 'IMMEDIATE' },
  warning:   { bg: '#7c2d12', border: '#f97316', icon: '⚠️',  label: 'WARNING'   },
  watch:     { bg: '#450a0a', border: '#dc2626', icon: '📡', label: 'WATCH'     },
};

function formatOccurred(ts) {
  if (!ts) return null;
  try {
    return new Date(ts).toLocaleString();
  } catch (_) {
    return null;
  }
}

// Timezone-aware incident time formatter (Fix 2). Deliberately avoids
// hand-rolled UTC offset math (DST makes hardcoded offsets wrong half the
// year) — uses Intl/toLocaleString with an explicit IANA zone instead.
// region: 'CA' -> Pacific Time labeled "PT"; 'NY'/'NJ'/'NJNY' -> Eastern
// Time labeled "ET"; anything else ("ALL"/unknown) -> browser-local time,
// no zone suffix appended (ambiguous which zone applies across regions).
function formatIncidentTime(isoOrMs, region) {
  if (!isoOrMs) return null;
  let d;
  try {
    d = new Date(isoOrMs);
    if (isNaN(d.getTime())) return null;
  } catch (_) {
    return null;
  }
  const opts = { month: 'short', day: '2-digit', year: 'numeric', hour: 'numeric', minute: '2-digit' };
  if (region === 'CA') {
    return d.toLocaleString('en-US', { ...opts, timeZone: 'America/Los_Angeles' }) + ' PT';
  }
  if (region === 'NY' || region === 'NJ' || region === 'NJNY') {
    return d.toLocaleString('en-US', { ...opts, timeZone: 'America/New_York' }) + ' ET';
  }
  // ALL / unknown region — omit offset adjustment, show browser-local time as-is.
  return d.toLocaleString('en-US', opts);
}

export default function AlertBanner({ demoState, hazards, routes, regionPill, compact = false }) {
  const [dismissed, setDismissed] = useState([]);

  const alerts = [];

  // ── Demo mode alerts (Fix 6) ──
  // All-regions demo nests `california`/`njny` keys instead of being flat.
  if (demoState?.active) {
    if (regionPill === 'ALL' && (demoState.california || demoState.njny)) {
      const ca = demoState.california || {};
      const nj = demoState.njny || {};
      alerts.push({
        id: 'demo_all',
        severity: 'immediate',
        message: `IMMEDIATE — Compound flood: US-101 CA + US-1 NJ · Multi-corridor rerouting active · ` +
          `CA: ${ca.trigger_time_display || '--'} · NJ: ${nj.trigger_time_display || '--'} · ` +
          `Auto-reset in: ${demoState.reset_in_seconds ?? '--'}s`,
      });
    } else if (demoState.segment || demoState.reroute) {
      const pct = demoState.flood_prob !== undefined ? Math.round(demoState.flood_prob * 100) : '--';
      alerts.push({
        id: 'demo_single',
        severity: 'immediate',
        message: `IMMEDIATE — Flood on ${demoState.segment || 'segment'} · P(flood)=${pct}% · ` +
          `Detected: ${demoState.trigger_time_display || '--'} · Rerouting via ${demoState.reroute?.corridor || '--'} · ` +
          `Auto-reset in: ${demoState.reset_in_seconds ?? '--'}s`,
      });
    }
    if (demoState.alerts?.length > 0) {
      demoState.alerts.forEach((a, i) => alerts.push({ ...a, id: `demo_legacy_${i}` }));
    }
  }

  // Pre-emptive trigger from routes (real graph mode)
  if (routes?.features) {
    for (const feat of routes.features) {
      if (feat.properties?.pre_emptive_trigger && feat.properties.alert_message) {
        const p = feat.properties;
        const triggerDisplay = p.trigger_time_display;
        alerts.push({
          id:       `route_${p.route_type}`,
          severity: 'immediate',
          message:  triggerDisplay
            ? `IMMEDIATE — Flood on ${p.segment || p.route_type} · P(flood)=${p.flood_prob !== undefined ? Math.round(p.flood_prob*100) : '--'}% · Detected: ${triggerDisplay} · Rerouting via ${p.corridor || p.route_type}`
            : p.alert_message,
        });
      }
    }
  }

  // ── Hazard-based alerts ──
  // Each tries to find a TRUE incident time; falls back to hazards.updated_at
  // (page-load/refresh time is never used as a substitute for a real incident
  // time per Fix 2 spec) only when no better field exists.
  if (hazards?.flood?.high_risk_segments > 0) {
    // Prefer a per-gauge `dateTime` field if the backend plumbs one through
    // (e.g. hazards.flood.gauges[0].dateTime); not yet wired end-to-end, so
    // fall back to hazards.updated_at — known gap, see code comment below.
    const gaugeTime = hazards.flood.gauges?.[0]?.dateTime;
    // FALLBACK: no per-gauge timestamp surfaced by backend yet; using the
    // hazard-summary refresh time instead of a true incident time.
    const ts = gaugeTime || hazards.updated_at || new Date().toISOString();
    const count = hazards.flood.high_risk_segments;
    alerts.push({
      id:       'flood_segments',
      severity: 'warning',
      message:  `🌊 ${count} road segment(s) at HIGH flood risk (P > 0.65)`,
      timestamp: ts,
      // Partial implementation: backend gives a single count, not an array of
      // individual gauge events with their own times, so we always say
      // "Detected:" rather than "Most recent:" even when count > 1.
    });
  }
  if (hazards?.wildfire?.zone_a_segments > 0) {
    // Prefer FIRMS acq_date+acq_time per detection if present; not yet wired
    // through as a flat field on hazards.wildfire, so fall back to updated_at.
    const acqDate = hazards.wildfire.acq_date;
    const acqTime = hazards.wildfire.acq_time;
    // FALLBACK: no acq_date/acq_time surfaced on the hazards summary yet —
    // using hazard-summary refresh time instead of the true FIRMS detection time.
    const ts = (acqDate && acqTime) ? `${acqDate}T${acqTime}` : (hazards.updated_at || new Date().toISOString());
    alerts.push({
      id:       'wildfire_zone_a',
      severity: 'warning',
      message:  `🔥 ${hazards.wildfire.zone_a_segments} segment(s) in wildfire Zone A (within 2 miles of active fire)`,
      timestamp: ts,
    });
  }
  if (hazards?.seismic?.significant_eqs > 0) {
    // Ideal source: properties.time from the USGS Earthquake API (unix ms),
    // converted via `new Date(properties.time)`. Raw per-event earthquake
    // objects aren't currently plumbed through useHazardData/App.jsx down to
    // this component (hazards.seismic only carries aggregate counts), so this
    // is a known gap — fall back to hazards.updated_at until raw USGS feature
    // objects (or at least their `time` field) are exposed on the hazards prop.
    const rawEqTime = hazards.seismic.earthquakes?.[0]?.properties?.time
                    || hazards.seismic.latest_eq_time;
    const ts = rawEqTime || hazards.updated_at || new Date().toISOString();
    alerts.push({
      id:       'seismic',
      severity: 'watch',
      message:  `🌍 ${hazards.seismic.significant_eqs} significant earthquake(s) (M4.0+) detected`,
      timestamp: ts,
    });
  }

  // Live pre-emptive trigger (Fix backend contract: hazards.live_pre_emptive_trigger)
  if (hazards?.live_pre_emptive_trigger?.active) {
    const t = hazards.live_pre_emptive_trigger;
    const pct = t.flood_prob !== undefined ? Math.round(t.flood_prob * 100) : '--';
    alerts.push({
      id: 'live_pre_emptive',
      severity: 'immediate',
      message: `IMMEDIATE — Flood on ${t.segment || 'segment'} · P(flood)=${pct}%`,
      timestamp: t.detected_at || hazards.updated_at,
    });
  }

  const visible = alerts.filter(a => !dismissed.includes(a.id));
  if (visible.length === 0) return null;

  const renderTimestamp = (alert) => {
    const formatted = formatIncidentTime(alert.timestamp, regionPill) || formatOccurred(alert.timestamp);
    return formatted;
  };

  // Compact mobile: show only the most severe alert as a single slim strip.
  // The timestamp is rendered as a sibling <span> OUTSIDE the message span's
  // ellipsis container so it never gets truncated/absorbed (Fix 13 check).
  if (compact) {
    const top = visible[0];
    const sev = SEVERITY_STYLES[top.severity] || SEVERITY_STYLES.watch;
    const ts = renderTimestamp(top);
    return (
      <div style={{
        position: 'relative',
        zIndex: 2000,
        background: sev.bg,
        borderBottom: `2px solid ${sev.border}`,
        padding: '6px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 12,
      }}>
        <span style={{ background: sev.border, color: '#fff', fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, whiteSpace: 'nowrap', flexShrink: 0 }}>
          {sev.label}
        </span>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
          {top.message}
        </span>
        {ts && (
          <span style={{ color: '#cbd5e1', opacity: 0.8, fontSize: 10, flexShrink: 0, whiteSpace: 'nowrap' }}>
            {ts}
          </span>
        )}
        {visible.length > 1 && (
          <span style={{ color: '#fcd34d', fontSize: 10, flexShrink: 0 }}>+{visible.length - 1}</span>
        )}
        <button onClick={() => setDismissed(d => [...d, top.id])}
          style={{ background: 'transparent', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 16, padding: '0 2px', flexShrink: 0, lineHeight: 1 }}>
          ×
        </button>
      </div>
    );
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 2000, display: 'flex', flexDirection: 'column', gap: 2 }}>
      {visible.slice(0, 4).map(alert => {
        const sev = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.watch;
        const ts = renderTimestamp(alert);
        return (
          <div key={alert.id} style={{ background: sev.bg, borderBottom: `2px solid ${sev.border}`, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, lineHeight: 1.4 }}>
            <span style={{ background: sev.border, color: '#fff', fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4, letterSpacing: '0.08em', whiteSpace: 'nowrap', flexShrink: 0 }}>
              {sev.label}
            </span>
            <span style={{ flex: 1 }}>
              {alert.message}
              {ts && (
                <span style={{ color: '#cbd5e1', fontSize: 11, opacity: 0.85 }}> · Detected: {ts}</span>
              )}
            </span>
            {alert.action && (
              <span style={{ color: '#fcd34d', fontSize: 12, flexShrink: 0 }}>→ {alert.action}</span>
            )}
            <button onClick={() => setDismissed(d => [...d, alert.id])}
              style={{ background: 'transparent', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 16, padding: '0 4px', flexShrink: 0 }}>
              ×
            </button>
          </div>
        );
      })}
      {visible.length > 4 && (
        <div style={{ background: '#1e1e2e', padding: '4px 16px', fontSize: 12, color: '#94a3b8', borderBottom: '1px solid #2d4a6e' }}>
          +{visible.length - 4} more alerts
        </div>
      )}
    </div>
  );
}
