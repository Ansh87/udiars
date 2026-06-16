/**
 * UDIARS App — root component.
 * Layout: [ControlPanel + AlertBanner + MapView] | [Sidebar]
 * WebSocket drives live MHRM updates every 60 seconds.
 */
import React, { useState, useEffect, useCallback } from 'react';
import MapView       from './components/MapView';
import Sidebar       from './components/Sidebar';
import ControlPanel  from './components/ControlPanel';
import AlertBanner   from './components/AlertBanner';
import useWebSocket  from './hooks/useWebSocket';
import useHazardData from './hooks/useHazardData';

export default function App() {
  const [tier, setTier] = useState(2);
  const [hazardVisibility, setHazardVisibility] = useState({
    flood:    true,
    wildfire: true,
    seismic:  true,
    mhrm:     true,
  });

  const {
    mhrm, hazards, routes, economic, health, demoState,
    lastUpdated, loading, error,
    loadInitialData, handleWsMessage,
    computeRoutes, startDemo, stopDemo, forceRefresh,
  } = useHazardData();

  // WebSocket live connection
  const { isConnected, reconnectCount } = useWebSocket(handleWsMessage);

  // Load initial data on mount
  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Toggle individual hazard layers
  const onHazardToggle = useCallback((key) => {
    setHazardVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Alert count badge in title
  useEffect(() => {
    const critCount = mhrm?.features?.filter(
      f => f.properties?.hazard_penalty >= 0.65
    ).length || 0;
    document.title = critCount > 0
      ? `⚠️ (${critCount}) UDIARS — California Multi-Hazard`
      : 'UDIARS — California Multi-Hazard';
  }, [mhrm]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100vw',
      overflow: 'hidden',
      background: '#0d1b2a',
    }}>
      {/* Alert banner — sits above everything */}
      <AlertBanner
        demoState={demoState}
        hazards={hazards}
        routes={routes}
      />

      {/* Main content row */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        {/* Map (full-screen-minus-sidebar) */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <MapView
            mhrm={mhrm}
            routes={routes}
            hazardVisibility={hazardVisibility}
          />

          {/* Control panel floats over the map */}
          <ControlPanel
            onRouteCompute={computeRoutes}
            onDemoStart={startDemo}
            onDemoStop={stopDemo}
            onForceRefresh={forceRefresh}
            onHazardToggle={onHazardToggle}
            demoState={demoState}
            hazardVisibility={hazardVisibility}
            isConnected={isConnected}
            lastUpdated={lastUpdated}
          />

          {/* Loading / error overlay */}
          {loading && (
            <div style={{
              position: 'absolute',
              bottom: 12,
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(13,27,42,0.9)',
              border: '1px solid #1e3a5c',
              borderRadius: 8,
              padding: '6px 14px',
              fontSize: 12,
              color: '#94a3b8',
              zIndex: 800,
            }}>
              ⏳ Loading hazard data…
            </div>
          )}

          {error && (
            <div style={{
              position: 'absolute',
              bottom: 12,
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(127,29,29,0.9)',
              border: '1px solid #ef4444',
              borderRadius: 8,
              padding: '6px 14px',
              fontSize: 12,
              color: '#fca5a5',
              zIndex: 800,
            }}>
              ⚠️ API error: {error} — running on last-known data
            </div>
          )}

          {/* WebSocket status */}
          {!isConnected && reconnectCount > 0 && (
            <div style={{
              position: 'absolute',
              bottom: 12,
              right: 14,
              background: 'rgba(13,27,42,0.9)',
              border: '1px solid #f97316',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 11,
              color: '#fb923c',
              zIndex: 800,
            }}>
              🔄 Reconnecting to live feed… ({reconnectCount})
            </div>
          )}

          {/* MHRM update ticker */}
          {mhrm?.metadata && (
            <div style={{
              position: 'absolute',
              bottom: 12,
              right: 14,
              background: 'rgba(13,27,42,0.85)',
              border: '1px solid #1e3a5c',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: 10,
              color: '#475569',
              zIndex: 750,
              textAlign: 'right',
            }}>
              MHRM · {mhrm.metadata.n_segments} segments · {mhrm.metadata.n_fire_detections} fires · {mhrm.metadata.n_earthquakes} EQs<br />
              Updated {mhrm.metadata.updated_at ? new Date(mhrm.metadata.updated_at).toLocaleTimeString() : '--'}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <Sidebar
          tier={tier}
          onTierChange={setTier}
          mhrm={mhrm}
          hazards={hazards}
          routes={routes}
          economic={economic}
          demoState={demoState}
          lastUpdated={lastUpdated}
          isConnected={isConnected}
        />
      </div>
    </div>
  );
}
