/**
 * useHazardData — fetches initial data from REST endpoints and exposes
 * update functions for the WebSocket message handler.
 */
import { useState, useCallback } from 'react';
import axios from 'axios';
import { REGION_PARAM_MAP } from '../constants/appData';

// Strip any trailing slash(es) so `${API}/route` never produces a double slash
// (a double slash in the path is a common cause of unexpected 404s behind proxies).
const API = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

function describeAxiosError(err, label) {
  if (err.response) {
    if (err.response.status === 404) {
      return `${label}: endpoint not found (404). Check that REACT_APP_API_URL ("${API}") points at the deployed backend with no typo or trailing slash.`;
    }
    return `${label}: server responded ${err.response.status} ${err.response.statusText || ''}`.trim();
  }
  if (err.request) {
    return `${label}: cannot reach backend at "${API}" — is it running and is REACT_APP_API_URL set correctly?`;
  }
  return `${label}: ${err.message}`;
}

// Maps internal pill value (CA/NJNY/ALL) to backend ?region= query param.
// Falls back to 'california' for unrecognized/undefined values so existing
// single-state callers (CA/NY/NJ) don't break — NY/NJ both map to njny.
function regionParam(regionPill) {
  if (!regionPill) return undefined;
  if (REGION_PARAM_MAP[regionPill]) return REGION_PARAM_MAP[regionPill];
  if (regionPill === 'NY' || regionPill === 'NJ') return 'njny';
  if (regionPill === 'CA') return 'california';
  return undefined;
}

export default function useHazardData() {
  const [mhrm,          setMhrm]          = useState(null);
  const [hazards,       setHazards]       = useState(null);
  const [routes,        setRoutes]        = useState(null);
  const [economic,      setEconomic]      = useState(null);
  const [health,        setHealth]        = useState(null);
  const [facilities,    setFacilities]    = useState(null);
  const [demoState,     setDemoState]     = useState({ active: false, alerts: [] });
  const [lastUpdated,   setLastUpdated]   = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState(null);

  // Initial data load — pass regionPill (CA/NJNY/ALL) to scope all REST calls.
  const loadInitialData = useCallback(async (regionPill) => {
    setLoading(true);
    setError(null);
    const region = regionParam(regionPill);
    const params = region ? { region } : {};
    try {
      const [mhrmRes, hazardsRes, economicRes, healthRes, facilitiesRes] = await Promise.allSettled([
        axios.get(`${API}/mhrm`, { params }),
        axios.get(`${API}/hazards`, { params }),
        axios.get(`${API}/economic`, { params }),
        axios.get(`${API}/health`),
        axios.get(`${API}/facilities`, { params }),
      ]);
      if (mhrmRes.status    === 'fulfilled') setMhrm(mhrmRes.value.data);
      if (hazardsRes.status === 'fulfilled') setHazards(hazardsRes.value.data);
      if (economicRes.status=== 'fulfilled') setEconomic(economicRes.value.data);
      if (healthRes.status  === 'fulfilled') setHealth(healthRes.value.data);
      if (facilitiesRes.status === 'fulfilled') setFacilities(facilitiesRes.value.data);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle incoming WebSocket messages
  const handleWsMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'initial_snapshot':
      case 'mhrm_update':
        if (msg.mhrm)          setMhrm(msg.mhrm);
        if (msg.hazard_summary) setHazards(msg.hazard_summary);
        if (msg.demo_state)    setDemoState(msg.demo_state);
        setLastUpdated(new Date());
        break;
      case 'pong':
      case 'heartbeat':
        setLastUpdated(new Date());
        break;
      default:
        break;
    }
  }, []);

  // Route computation
  const computeRoutes = useCallback(async (originLat, originLng, destLat, destLng, regionPill) => {
    try {
      const region = regionParam(regionPill);
      const res = await axios.get(`${API}/route`, {
        params: {
          origin_lat: originLat, origin_lng: originLng,
          dest_lat: destLat, dest_lng: destLng,
          ...(region ? { region } : {}),
        },
      });
      setRoutes(res.data);
      setError(null);
      return res.data;
    } catch (err) {
      // Friendly UI-facing message — never surface raw status codes (e.g. "404")
      // to the user. Full diagnostic detail still goes to console for debugging.
      const detail = describeAxiosError(err, 'Compute Routes');
      console.error(detail);
      setError('Route computation temporarily unavailable — please retry');
      return null;
    }
  }, []);

  // Region-scoped demo trigger. Picks the matching endpoint per pill.
  const startDemo = useCallback(async (regionPill) => {
    try {
      const path = regionPill === 'NJNY' ? '/demo/flood/njny'
                 : regionPill === 'ALL'  ? '/demo/flood/all'
                 : '/demo/flood';
      const res = await axios.post(`${API}${path}`);
      setDemoState({ active: true, ...res.data });
      setError(null);
      return res.data;
    } catch (err) {
      const detail = describeAxiosError(err, 'Demo Start');
      console.error(detail);
      setError('Demo activation temporarily unavailable — please retry');
      return null;
    }
  }, []);

  const startDemoCA    = useCallback(() => startDemo('CA'), [startDemo]);
  const startDemoNJNY  = useCallback(() => startDemo('NJNY'), [startDemo]);
  const startDemoAll   = useCallback(() => startDemo('ALL'), [startDemo]);

  const stopDemo = useCallback(async () => {
    try {
      await axios.post(`${API}/demo/stop`);
    } catch (err) {
      // Demo auto-resets server-side after 60s regardless; swallow errors here
      // since this is also called client-side as a local countdown cleanup.
      console.error(describeAxiosError(err, 'Demo Stop'));
    } finally {
      setDemoState({ active: false, alerts: [] });
      setError(null);
    }
  }, []);

  // Zone-override demo endpoints (Fix 9/12)
  const activateZone = useCallback(async (zone) => {
    try {
      const path = zone === 'clear' ? '/demo/zone/clear' : `/demo/zone/${zone}`;
      await axios.post(`${API}${path}`);
      setError(null);
    } catch (err) {
      console.error(describeAxiosError(err, `Zone ${zone}`));
      setError('Zone override temporarily unavailable — please retry');
    }
  }, []);

  // Force refresh
  const forceRefresh = useCallback(async (regionPill) => {
    try {
      await axios.post(`${API}/refresh`);
      await loadInitialData(regionPill);
      setError(null);
    } catch (err) {
      console.error(describeAxiosError(err, 'Refresh'));
      setError('Refresh temporarily unavailable — please retry');
    }
  }, [loadInitialData]);

  return {
    mhrm, hazards, routes, economic, health, facilities, demoState, lastUpdated,
    loading, error,
    loadInitialData, handleWsMessage,
    computeRoutes, startDemo, startDemoCA, startDemoNJNY, startDemoAll,
    stopDemo, forceRefresh, activateZone,
    setRoutes, setDemoState,
  };
}
