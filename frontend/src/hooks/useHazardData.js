/**
 * useHazardData — fetches initial data from REST endpoints and exposes
 * update functions for the WebSocket message handler.
 */
import { useState, useCallback } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function useHazardData() {
  const [mhrm,          setMhrm]          = useState(null);
  const [hazards,       setHazards]       = useState(null);
  const [routes,        setRoutes]        = useState(null);
  const [economic,      setEconomic]      = useState(null);
  const [health,        setHealth]        = useState(null);
  const [demoState,     setDemoState]     = useState({ active: false, alerts: [] });
  const [lastUpdated,   setLastUpdated]   = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState(null);

  // Initial data load
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mhrmRes, hazardsRes, economicRes, healthRes] = await Promise.allSettled([
        axios.get(`${API}/mhrm`),
        axios.get(`${API}/hazards`),
        axios.get(`${API}/economic`),
        axios.get(`${API}/health`),
      ]);
      if (mhrmRes.status    === 'fulfilled') setMhrm(mhrmRes.value.data);
      if (hazardsRes.status === 'fulfilled') setHazards(hazardsRes.value.data);
      if (economicRes.status=== 'fulfilled') setEconomic(economicRes.value.data);
      if (healthRes.status  === 'fulfilled') setHealth(healthRes.value.data);
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
  const computeRoutes = useCallback(async (originLat, originLng, destLat, destLng) => {
    try {
      const res = await axios.get(`${API}/route`, {
        params: { origin_lat: originLat, origin_lng: originLng, dest_lat: destLat, dest_lng: destLng },
      });
      setRoutes(res.data);
      return res.data;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  // Demo mode
  const startDemo = useCallback(async () => {
    try {
      await axios.post(`${API}/demo/start`);
      const res = await axios.get(`${API}/demo/status`);
      setDemoState(res.data);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const stopDemo = useCallback(async () => {
    try {
      await axios.post(`${API}/demo/stop`);
      setDemoState({ active: false, alerts: [] });
    } catch (err) {
      setError(err.message);
    }
  }, []);

  // Force refresh
  const forceRefresh = useCallback(async () => {
    try {
      await axios.post(`${API}/refresh`);
      await loadInitialData();
    } catch (err) {
      setError(err.message);
    }
  }, [loadInitialData]);

  return {
    mhrm, hazards, routes, economic, health, demoState, lastUpdated,
    loading, error,
    loadInitialData, handleWsMessage,
    computeRoutes, startDemo, stopDemo, forceRefresh,
    setRoutes,
  };
}
