import { useEffect, useRef, useCallback, useState } from 'react';
import type { WsMessage } from '../types/ws';

const MIN_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

interface UseWebSocketOptions {
  onMessage: (msg: WsMessage) => void;
  token: string | null;
  onOpen?: () => void;
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

  useEffect(() => { onMessageRef.current = onMessage; });
  useEffect(() => { onOpenRef.current = onOpen; });
  useEffect(() => { tokenRef.current = token; });

  const connect = useCallback(() => {
    if (unmountedRef.current || !tokenRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(tokenRef.current)}`;

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
      reconnectTimerRef.current = setTimeout(connect, delay);
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
    connect();

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
