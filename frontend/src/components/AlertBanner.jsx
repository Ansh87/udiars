/**
 * AlertBanner — top-of-screen alert strip.
 * Shows pre-emptive trigger alerts, color-coded by severity.
 * Auto-collapses when no active alerts.
 */
import React, { useState } from 'react';

const SEVERITY_STYLES = {
  immediate: { bg: '#7f1d1d', border: '#ef4444', icon: '🚨', label: 'IMMEDIATE' },
  warning:   { bg: '#7c2d12', border: '#f97316', icon: '⚠️',  label: 'WARNING'   },
  watch:     { bg: '#713f12', border: '#eab308', icon: '📡', label: 'WATCH'     },
};

export default function AlertBanner({ demoState, hazards, routes }) {
  const [dismissed, setDismissed] = useState([]);

  const alerts = [];

  // Demo mode alerts
  if (demoState?.active && demoState.alerts?.length > 0) {
    demoState.alerts.forEach((a, i) => alerts.push({ ...a, id: `demo_${i}` }));
  }

  // Pre-emptive trigger from routes
  if (routes?.features) {
    for (const feat of routes.features) {
      if (feat.properties?.pre_emptive_trigger && feat.properties.alert_message) {
        alerts.push({
          id:       `route_${feat.properties.route_type}`,
          severity: 'immediate',
          message:  feat.properties.alert_message,
        });
      }
    }
  }

  // Hazard-based alerts
  if (hazards?.flood?.high_risk_segments > 0) {
    alerts.push({
      id:       'flood_segments',
      severity: 'warning',
      message:  `🌊 ${hazards.flood.high_risk_segments} road segment(s) at HIGH flood risk (P > 0.65)`,
    });
  }
  if (hazards?.wildfire?.zone_a_segments > 0) {
    alerts.push({
      id:       'wildfire_zone_a',
      severity: 'warning',
      message:  `🔥 ${hazards.wildfire.zone_a_segments} segment(s) in wildfire Zone A (within 2 miles of active fire)`,
    });
  }
  if (hazards?.seismic?.significant_eqs > 0) {
    alerts.push({
      id:       'seismic',
      severity: 'watch',
      message:  `🌍 ${hazards.seismic.significant_eqs} significant earthquake(s) (M4.0+) detected in California`,
    });
  }

  const visible = alerts.filter(a => !dismissed.includes(a.id));
  if (visible.length === 0) return null;

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 2000,
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    }}>
      {visible.slice(0, 4).map(alert => {
        const sev = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.watch;
        return (
          <div
            key={alert.id}
            style={{
              background: sev.bg,
              borderBottom: `2px solid ${sev.border}`,
              padding: '8px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 13,
              lineHeight: 1.4,
            }}
          >
            <span style={{
              background: sev.border,
              color: '#fff',
              fontSize: 10,
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: 4,
              letterSpacing: '0.08em',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}>
              {sev.label}
            </span>
            <span style={{ flex: 1 }}>{alert.message}</span>
            {alert.action && (
              <span style={{ color: '#fcd34d', fontSize: 12, flexShrink: 0 }}>
                → {alert.action}
              </span>
            )}
            <button
              onClick={() => setDismissed(d => [...d, alert.id])}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#9ca3af',
                cursor: 'pointer',
                fontSize: 16,
                padding: '0 4px',
                flexShrink: 0,
              }}
            >×</button>
          </div>
        );
      })}
      {visible.length > 4 && (
        <div style={{
          background: '#1e1e2e',
          padding: '4px 16px',
          fontSize: 12,
          color: '#94a3b8',
          borderBottom: '1px solid #2d4a6e',
        }}>
          +{visible.length - 4} more alerts
        </div>
      )}
    </div>
  );
}
