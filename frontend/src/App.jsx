/**
 * UDIARS App — root component.
 * Desktop: map + right sidebar
 * Mobile:  full-screen map + bottom sheet + bottom nav bar
 */
import React, { useState, useEffect, useCallback } from 'react';
import MapView       from './components/MapView';
import Sidebar       from './components/Sidebar';
import ControlPanel  from './components/ControlPanel';
import AlertBanner   from './components/AlertBanner';
import HelpModal     from './components/HelpModal';
import TipsModal      from './components/TipsModal';
import ReadMeModal   from './components/ReadMeModal';
import useWebSocket  from './hooks/useWebSocket';
import useHazardData from './hooks/useHazardData';
import useIsMobile   from './hooks/useIsMobile';

// Bottom nav tabs for mobile
const MOBILE_TABS = [
  { id: 'map',      icon: '🗺',  label: 'Map'     },
  { id: 'routes',   icon: '🚗',  label: 'Routes'  },
  { id: 'hazards',  icon: '⚡',  label: 'Hazards' },
  { id: 'settings', icon: '⚙️',  label: 'Controls'},
];

export default function App() {
  const isMobile = useIsMobile();
  const [tier, setTier]               = useState(2);
  const [mobileTab, setMobileTab]     = useState('map');
  const [sheetOpen, setSheetOpen]     = useState(false);
  const [region, setRegion]           = useState('CA');
  const [activeModal, setActiveModal] = useState(null); // 'help' | 'tips' | 'readme' | null
  const [hazardVisibility, setHazardVisibility] = useState({
    flood: true, wildfire: true, seismic: true, mhrm: true,
  });

  const {
    mhrm, hazards, routes, economic, demoState,
    lastUpdated, loading, error,
    loadInitialData, handleWsMessage,
    computeRoutes, startDemo, stopDemo, forceRefresh,
  } = useHazardData();

  const { isConnected, reconnectCount } = useWebSocket(handleWsMessage);

  useEffect(() => { loadInitialData(); }, [loadInitialData]);

  const onHazardToggle = useCallback((key) => {
    setHazardVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Open bottom sheet when switching to non-map tabs on mobile
  const handleMobileTab = (id) => {
    setMobileTab(id);
    setSheetOpen(id !== 'map');
  };

  useEffect(() => {
    const critCount = mhrm?.features?.filter(
      f => f.properties?.hazard_penalty >= 0.65
    ).length || 0;
    document.title = critCount > 0
      ? `⚠️ (${critCount}) UDIARS — CA/NY/NJ`
      : 'UDIARS — Multi-State Hazard POC';
  }, [mhrm]);

  // ── MOBILE LAYOUT ──────────────────────────────────────────────────────────
  if (isMobile) {
    const BOTTOM_NAV_H = 56;
    const SHEET_H = sheetOpen ? '60vh' : 0;

    return (
      <div style={{ height: '100dvh', width: '100vw', overflow: 'hidden', background: '#0d1b2a', display: 'flex', flexDirection: 'column', position: 'relative' }}>

        {/* Alert banner */}
        <AlertBanner demoState={demoState} hazards={hazards} routes={routes} compact />

        {/* Full-screen map */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <MapView mhrm={mhrm} routes={routes} hazardVisibility={hazardVisibility} region={region} />

          {/* Status chip top-right */}
          <div style={{
            position: 'absolute', top: 10, right: 10, zIndex: 900,
            display: 'flex', gap: 6, alignItems: 'center',
          }}>
            {demoState?.active && (
              <span className="badge badge-brown pulse-brown" style={{ fontSize: 10 }}>DEMO</span>
            )}
            <div style={{
              background: 'rgba(13,27,42,0.88)',
              border: `1px solid ${isConnected ? '#22c55e' : '#f97316'}`,
              borderRadius: 20, padding: '4px 10px',
              fontSize: 11, color: isConnected ? '#22c55e' : '#fb923c',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: isConnected ? '#22c55e' : '#f97316' }} />
              {isConnected ? 'LIVE' : 'Reconnecting…'}
            </div>
          </div>

          {/* Quick hazard chips bottom-left (above nav) */}
          {hazards?.compound && (
            <div style={{
              position: 'absolute',
              bottom: BOTTOM_NAV_H + (sheetOpen ? 0 : 8),
              left: 10, zIndex: 900,
              display: 'flex', gap: 6, flexWrap: 'wrap', maxWidth: '60vw',
              transition: 'bottom 0.3s ease',
            }}>
              {hazards.compound.critical_segments > 0 && (
                <span className="badge badge-red" style={{ fontSize: 10 }}>
                  🚨 {hazards.compound.critical_segments} critical
                </span>
              )}
              {hazards.wildfire?.zone_a_segments > 0 && (
                <span className="badge badge-orange" style={{ fontSize: 10 }}>
                  🔥 Zone A
                </span>
              )}
              {hazards.seismic?.significant_eqs > 0 && (
                <span className="badge badge-purple" style={{ fontSize: 10 }}>
                  🌍 M4+ EQ
                </span>
              )}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', background: 'rgba(13,27,42,0.9)', borderRadius: 8, padding: '8px 16px', fontSize: 12, color: '#94a3b8', zIndex: 800 }}>
              ⏳ Loading…
            </div>
          )}
        </div>

        {/* Bottom sheet */}
        <div style={{
          position: 'absolute',
          bottom: BOTTOM_NAV_H,
          left: 0, right: 0,
          height: SHEET_H,
          background: '#0d1b2a',
          borderTop: '1px solid #1e3a5c',
          borderRadius: '16px 16px 0 0',
          overflow: 'hidden',
          transition: 'height 0.3s ease',
          zIndex: 1100,
          display: 'flex',
          flexDirection: 'column',
        }}>
          {/* Drag handle */}
          {sheetOpen && (
            <div
              onClick={() => setSheetOpen(false)}
              style={{ padding: '10px 0 6px', display: 'flex', justifyContent: 'center', cursor: 'pointer', flexShrink: 0 }}
            >
              <div style={{ width: 36, height: 4, borderRadius: 2, background: '#2d4a6e' }} />
            </div>
          )}

          {sheetOpen && (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {(mobileTab === 'routes' || mobileTab === 'hazards') && (
                <Sidebar
                  tier={mobileTab === 'routes' ? 1 : mobileTab === 'hazards' ? 2 : 3}
                  onTierChange={setTier}
                  mhrm={mhrm} hazards={hazards} routes={routes} economic={economic}
                  demoState={demoState} lastUpdated={lastUpdated} isConnected={isConnected}
                  mobile
                />
              )}
              {mobileTab === 'settings' && (
                <div style={{ padding: '0 12px 12px' }}>
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
                    region={region}
                    onRegionChange={setRegion}
                    onOpenHelp={() => setActiveModal('help')}
                    onOpenTips={() => setActiveModal('tips')}
                    onOpenReadMe={() => setActiveModal('readme')}
                    mobile
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Bottom navigation bar */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: BOTTOM_NAV_H,
          background: '#0d1b2a',
          borderTop: '1px solid #1e3a5c',
          display: 'flex',
          zIndex: 1200,
        }}>
          {MOBILE_TABS.map(tab => {
            const active = mobileTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleMobileTab(tab.id)}
                style={{
                  flex: 1, border: 'none',
                  background: active ? 'rgba(59,130,246,0.12)' : 'transparent',
                  color: active ? '#60a5fa' : '#64748b',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  gap: 3, cursor: 'pointer', fontSize: 18,
                  borderTop: active ? '2px solid #3b82f6' : '2px solid transparent',
                  transition: 'all 0.15s',
                  WebkitTapHighlightColor: 'transparent',
                }}
              >
                <span>{tab.icon}</span>
                <span style={{ fontSize: 10, fontWeight: active ? 600 : 400 }}>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {activeModal === 'help'   && <HelpModal   onClose={() => setActiveModal(null)} mobile />}
        {activeModal === 'tips'   && <TipsModal   onClose={() => setActiveModal(null)} mobile />}
        {activeModal === 'readme' && <ReadMeModal onClose={() => setActiveModal(null)} mobile />}
      </div>
    );
  }

  // ── DESKTOP LAYOUT ─────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden', background: '#0d1b2a' }}>
      <AlertBanner demoState={demoState} hazards={hazards} routes={routes} />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <MapView mhrm={mhrm} routes={routes} hazardVisibility={hazardVisibility} region={region} />

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
            region={region}
            onRegionChange={setRegion}
            onOpenHelp={() => setActiveModal('help')}
            onOpenTips={() => setActiveModal('tips')}
            onOpenReadMe={() => setActiveModal('readme')}
          />

          {loading && (
            <div style={{ position: 'absolute', bottom: 12, left: '50%', transform: 'translateX(-50%)', background: 'rgba(13,27,42,0.9)', border: '1px solid #1e3a5c', borderRadius: 8, padding: '6px 14px', fontSize: 12, color: '#94a3b8', zIndex: 800 }}>
              ⏳ Loading hazard data…
            </div>
          )}
          {error && (
            <div style={{ position: 'absolute', bottom: 12, left: '50%', transform: 'translateX(-50%)', background: 'rgba(127,29,29,0.9)', border: '1px solid #ef4444', borderRadius: 8, padding: '6px 14px', fontSize: 12, color: '#fca5a5', zIndex: 800 }}>
              ⚠️ {error} — running on last-known data
            </div>
          )}
          {!isConnected && reconnectCount > 0 && (
            <div style={{ position: 'absolute', bottom: 12, right: 14, background: 'rgba(13,27,42,0.9)', border: '1px solid #f97316', borderRadius: 8, padding: '6px 12px', fontSize: 11, color: '#fb923c', zIndex: 800 }}>
              🔄 Reconnecting… ({reconnectCount})
            </div>
          )}
          {mhrm?.metadata && (
            <div style={{ position: 'absolute', bottom: 12, right: 14, background: 'rgba(13,27,42,0.92)', border: '1px solid #2d4a6e', borderRadius: 6, padding: '4px 10px', fontSize: 10, color: '#cbd5e1', zIndex: 750, textAlign: 'right' }}>
              MHRM (compound risk model) · {mhrm.metadata.n_segments} segs · {mhrm.metadata.n_fire_detections} fires · {mhrm.metadata.n_earthquakes} EQs<br />
              Updated: {mhrm.metadata.updated_at ? new Date(mhrm.metadata.updated_at).toLocaleTimeString() : '--'}
            </div>
          )}
        </div>

        <Sidebar
          tier={tier} onTierChange={setTier}
          mhrm={mhrm} hazards={hazards} routes={routes} economic={economic}
          demoState={demoState} lastUpdated={lastUpdated} isConnected={isConnected}
        />
      </div>

      {activeModal === 'help'   && <HelpModal   onClose={() => setActiveModal(null)} mobile={isMobile} />}
      {activeModal === 'tips'   && <TipsModal   onClose={() => setActiveModal(null)} mobile={isMobile} />}
      {activeModal === 'readme' && <ReadMeModal onClose={() => setActiveModal(null)} mobile={isMobile} />}
    </div>
  );
}
