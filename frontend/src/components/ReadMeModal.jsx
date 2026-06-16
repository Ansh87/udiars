/**
 * ReadMeModal — explains how the app works.
 */
import React from 'react';
import Modal from './Modal';
import { TIER_INFO } from '../constants/appData';

export default function ReadMeModal({ onClose, mobile = false }) {
  return (
    <Modal title="📖 Read Me — How UDIARS Works" onClose={onClose} mobile={mobile}>
      <p style={{ color: '#cbd5e1' }}>
        <b>UDIARS</b> (Unified Disaster Intelligence &amp; Adaptive Response System) is a proof-of-concept
        that fuses live flood, wildfire, and earthquake data into one risk score per road segment, then
        routes around the highest-risk roads in real time.
      </p>

      <div style={{ fontWeight: 700, marginTop: 12, marginBottom: 4 }}>1. Pick a region</div>
      <p style={{ color: '#94a3b8' }}>
        Use the state selector to focus the map on California, New York, or New Jersey. The map zooms to
        bring the selected state into frame; hazard data for all three states loads in the background.
      </p>

      <div style={{ fontWeight: 700, marginTop: 12, marginBottom: 4 }}>2. The Multi-Hazard Risk Map (MHRM)</div>
      <p style={{ color: '#94a3b8' }}>
        Each colored circle on the map is a road segment scored on a 0–100% <b>compound risk</b> — the
        combined effect of flood probability, wildfire zone proximity, and earthquake shaking intensity at
        that location. Green is low risk, red is critical.
      </p>

      <div style={{ fontWeight: 700, marginTop: 12, marginBottom: 4 }}>3. Compute a route</div>
      <p style={{ color: '#94a3b8' }}>
        Enter or search an origin and destination (or pick a preset), then tap "Compute Routes." UDIARS
        returns a primary route plus two independent alternates, each weighted to avoid high-risk segments.
        If a route crosses a critical hazard, a pre-emptive reroute alert fires automatically.
      </p>

      <div style={{ fontWeight: 700, marginTop: 12, marginBottom: 4 }}>4. Demo mode</div>
      <p style={{ color: '#94a3b8' }}>
        "Demo: LA-101 Flood" simulates a live flash-flood event on US-101 in Los Angeles so you can see
        alerts, rerouting, and the economic impact dashboard react in real time without waiting for an
        actual disaster.
      </p>

      <div style={{ fontWeight: 700, marginTop: 12, marginBottom: 4 }}>5. The three view tiers</div>
      {TIER_INFO.map((t, i) => (
        <p key={t.label} style={{ color: '#94a3b8', margin: '4px 0' }}>
          <b style={{ color: '#e2e8f0' }}>T{i + 1} · {t.label}:</b> {t.full}
        </p>
      ))}

      <div style={{ fontWeight: 700, marginTop: 12, marginBottom: 4 }}>6. Economic Impact tab</div>
      <p style={{ color: '#94a3b8' }}>
        Found under Tier 3 → Economic. Estimates infrastructure losses — highway closure costs and bridge
        damage (using HAZUS-MH style fragility curves) — driven by current hazard levels. It will show "no
        significant impact" when hazard levels are low; that's expected, not a bug.
      </p>

      <p style={{ color: '#64748b', fontSize: 11, marginTop: 14 }}>
        This is a proof-of-concept. Synthetic data is used whenever a live government data feed (USGS,
        NOAA, NASA FIRMS) is unavailable, so results should not be used for real evacuation decisions.
      </p>
    </Modal>
  );
}
