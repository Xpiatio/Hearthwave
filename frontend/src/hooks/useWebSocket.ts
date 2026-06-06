import { useEffect, useRef, useCallback, useState } from 'react';
import type { WsMessage } from '../types/ws';

const MIN_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

interface UseWebSocketOptions {
  onMessage: (msg: WsMessage) => void;
  token: string | null;
  onOpen?: () => void;
}

async function fetchWsTicket(token: string): Promise<string | null> {
  try {
    const resp = await fetch('/auth/ws-ticket', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return null;
    const data = await resp.json() as { ticket?: string };
    return data.ticket ?? null;
  } catch {
    return null;
  }
}

export function useWebSocket({ onMessage, token, onOpen }: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(MIN_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const tokenRef = useRef(token);
  const unmountedRef = useRef(false);

  // Keep callback refs current without re-triggering connect effect
  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onOpenRef.current = onOpen; }, [onOpen]);
  useEffect(() => { tokenRef.current = token; }, [token]);

  const connect = useCallback(async () => {
    if (unmountedRef.current || !tokenRef.current) return;

    const currentToken = tokenRef.current;

    // Fetch a one-time ticket so the long-lived token never appears in the
    // WS upgrade URL (and therefore never in nginx access logs).
    // Fall back to the raw token if the ticket endpoint is unreachable.
    const ticket = await fetchWsTicket(currentToken);
    if (unmountedRef.current || tokenRef.current !== currentToken) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const param = ticket
      ? `ticket=${encodeURIComponent(ticket)}`
      : `token=${encodeURIComponent(currentToken)}`;
    const url = `${protocol}//${window.location.host}/ws?${param}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      setConnected(true);
      backoffRef.current = MIN_BACKOFF_MS;
      onOpenRef.current?.();
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as WsMessage;
        onMessageRef.current(msg);
      } catch {
        // Ignore unparseable frames
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      if (unmountedRef.current) return;
      // 4001 = auth failure — don't reconnect
      if (event.code === 4001) return;
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(() => { void connect(); }, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    if (!token) {
      // No token: close any existing connection.
      if (reconnectTimerRef.current !== null) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
      return;
    }

    unmountedRef.current = false;
    backoffRef.current = MIN_BACKOFF_MS;
    void connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current !== null) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect, token]);

  const send = useCallback((payload: unknown) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  return { send, connected };
}
