import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  WsMessage,
  StatusMsg,
  FamilyPresenceEntry,
  NeighborhoodStateMsg,
  StoredStreamMsg,
  DisplayAckMsg,
} from '../types/ws';
import type { ChatEntry } from '../components/ChatDisplay/ChatDisplay';

const MIN_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;
// Memory-bounded for overnight running — the kiosk display shows only the
// last 3 anyway; 20 gives a little headroom without growing unbounded.
const MESSAGE_CAP = 20;

export interface DisplayAlert {
  kind: 'weather' | 'street';
  message: string;
  ts: string;
}

// A display_ack, tagged with a monotonic seq so consumers can react to it
// via useEffect even when the same action fires twice in a row (a plain
// `{action}` object would look identical to React's dependency comparison).
export interface DisplayAckEvent {
  action: DisplayAckMsg['action'];
  seq: number;
}

export interface UseDisplaySocketResult {
  connected: boolean;
  authFailed: boolean;
  status: StatusMsg | null;
  presence: FamilyPresenceEntry[];
  neighborhood: NeighborhoodStateMsg | null;
  messages: ChatEntry[];
  alert: DisplayAlert | null;
  lastAck: DisplayAckEvent | null;
  send: (msg: object) => void;
}

let entryCounter = 0;
function nextId(): string {
  return `display-msg-${++entryCounter}`;
}

function formatTime(iso?: string): string {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function capMessages(entries: ChatEntry[]): ChatEntry[] {
  return entries.length > MESSAGE_CAP ? entries.slice(entries.length - MESSAGE_CAP) : entries;
}

// Mirrors App.tsx's streamMsgToEntry (live tx_echo / chat_echo / rx_message
// handling), kept local so this hook has no dependency on the operator App.
function streamMsgToEntry(msg: StoredStreamMsg): ChatEntry {
  if (msg.type === 'tx_echo') {
    const recipient =
      msg.target_call && msg.target_call !== 'ALL'
        ? (msg.target_name ? `${msg.target_call} — ${msg.target_name}` : msg.target_call)
        : undefined;
    return {
      id: nextId(),
      timestamp: formatTime(msg.ts),
      kind: 'tx',
      sender: msg.display_name || msg.operator || msg.callsign,
      recipient,
      text: msg.text,
    };
  }
  if (msg.type === 'chat_echo') {
    return {
      id: nextId(),
      timestamp: formatTime(msg.ts),
      kind: 'chat',
      sender: msg.display_name || msg.operator || msg.callsign,
      text: msg.text,
    };
  }
  // rx_message
  return {
    id: nextId(),
    timestamp: formatTime(msg.ts),
    kind: 'rx',
    sender: msg.from || msg.callsign || undefined,
    text: msg.text,
    callsign_spans: msg.callsign_spans,
    source: msg.source,
  };
}

/**
 * WS hook for the kiosk /display route. Authenticates with a long-lived
 * device token (query param, no /auth/ws-ticket exchange — the token itself
 * is the credential the server checks and can revoke). No user login.
 */
export function useDisplaySocket(token: string | null): UseDisplaySocketResult {
  const [connected, setConnected] = useState(false);
  const [authFailed, setAuthFailed] = useState(false);
  const [status, setStatus] = useState<StatusMsg | null>(null);
  const [presence, setPresence] = useState<FamilyPresenceEntry[]>([]);
  const [neighborhood, setNeighborhood] = useState<NeighborhoodStateMsg | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [alert, setAlert] = useState<DisplayAlert | null>(null);
  const [lastAck, setLastAck] = useState<DisplayAckEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const ackSeqRef = useRef(0);
  const backoffRef = useRef(MIN_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const appendMessage = useCallback((entry: ChatEntry) => {
    setMessages((prev) => capMessages([...prev, entry]));
  }, []);

  const handleMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'status':
        setStatus(msg);
        break;
      case 'family_presence':
        setPresence(msg.entries);
        break;
      case 'neighborhood_state':
        setNeighborhood(msg);
        break;
      case 'chat_history':
        setMessages(capMessages(msg.messages.map(streamMsgToEntry)));
        break;
      case 'chat_cleared':
        setMessages([]);
        break;
      case 'chat_echo':
      case 'tx_echo':
        appendMessage(streamMsgToEntry(msg));
        break;
      case 'rx_message':
        if (!msg.partial) appendMessage(streamMsgToEntry(msg));
        break;
      case 'ncs_alert':
        setAlert({ kind: 'weather', message: msg.headline, ts: new Date().toISOString() });
        break;
      case 'neighborhood_alert':
        setAlert({ kind: 'street', message: msg.message, ts: msg.ts });
        break;
      case 'display_ack':
        ackSeqRef.current += 1;
        setLastAck({ action: msg.action, seq: ackSeqRef.current });
        break;
      default:
        break;
    }
  }, [appendMessage]);

  const connect = useCallback(() => {
    if (unmountedRef.current || !token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws?device_token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      setConnected(true);
      backoffRef.current = MIN_BACKOFF_MS;
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as WsMessage;
        handleMessage(msg);
      } catch {
        // Ignore unparseable frames
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      if (unmountedRef.current) return;
      // 4001 = auth failure — don't reconnect
      if (event.code === 4001) {
        setAuthFailed(true);
        return;
      }
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(() => { connect(); }, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [token, handleMessage]);

  useEffect(() => {
    if (!token) {
      if (reconnectTimerRef.current !== null) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
      setAuthFailed(false);
      return;
    }

    unmountedRef.current = false;
    backoffRef.current = MIN_BACKOFF_MS;
    setAuthFailed(false);
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

  const send = useCallback((payload: object) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  return { connected, authFailed, status, presence, neighborhood, messages, alert, lastAck, send };
}
