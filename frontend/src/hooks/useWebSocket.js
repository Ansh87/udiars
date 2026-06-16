/**
 * useWebSocket — connects to /ws/updates and maintains auto-reconnect.
 * Returns: { lastMessage, isConnected, reconnectCount }
 */
import { useState, useEffect, useRef, useCallback } from 'react';

// Auto-upgrade to wss:// on HTTPS (Railway / production)
const WS_URL = process.env.REACT_APP_WS_URL || (
  typeof window !== 'undefined' && window.location.protocol === 'https:'
    ? `wss://${window.location.hostname}/ws/updates`
    : 'ws://localhost:8000/ws/updates'
);
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_DELAY = 30000;

export default function useWebSocket(onMessage) {
  const [isConnected, setIsConnected]     = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const wsRef           = useRef(null);
  const reconnectDelay  = useRef(RECONNECT_DELAY_MS);
  const reconnectTimer  = useRef(null);
  const mountedRef      = useRef(true);
  const onMessageRef    = useRef(onMessage);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current && wsRef.current.readyState < 2) {
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        console.log('[UDIARS WS] Connected');
        setIsConnected(true);
        reconnectDelay.current = RECONNECT_DELAY_MS;
        setReconnectCount(0);

        // Send ping every 25 seconds to keep-alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          } else {
            clearInterval(pingInterval);
          }
        }, 25000);
        ws._pingInterval = pingInterval;
      };

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (onMessageRef.current) onMessageRef.current(data);
        } catch (err) {
          console.warn('[UDIARS WS] Parse error:', err);
        }
      };

      ws.onerror = (err) => {
        console.warn('[UDIARS WS] Error:', err);
      };

      ws.onclose = (evt) => {
        if (!mountedRef.current) return;
        if (ws._pingInterval) clearInterval(ws._pingInterval);
        setIsConnected(false);
        console.log(`[UDIARS WS] Closed (code ${evt.code}) — reconnecting in ${reconnectDelay.current}ms`);
        reconnectTimer.current = setTimeout(() => {
          if (!mountedRef.current) return;
          setReconnectCount(c => c + 1);
          connect();
        }, reconnectDelay.current);
        reconnectDelay.current = Math.min(reconnectDelay.current * 1.5, MAX_RECONNECT_DELAY);
      };
    } catch (err) {
      console.error('[UDIARS WS] Failed to create WebSocket:', err);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const sendMessage = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { isConnected, reconnectCount, sendMessage };
}
