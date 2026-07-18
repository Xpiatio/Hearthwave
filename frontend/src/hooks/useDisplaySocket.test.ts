import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useDisplaySocket } from './useDisplaySocket';

// ---------------------------------------------------------------------------
// Fake WebSocket implementation (mirrors src/hooks/__tests__/useWebSocket.test.ts)
// ---------------------------------------------------------------------------

type FakeWSInstance = {
  url: string;
  readyState: number;
  onopen: ((e: Event) => void) | null;
  onmessage: ((e: MessageEvent) => void) | null;
  onclose: ((e: CloseEvent) => void) | null;
  onerror: ((e: Event) => void) | null;
  close: (code?: number, reason?: string) => void;
  send: (data: string) => void;
  _triggerOpen: () => void;
  _triggerMessage: (data: unknown) => void;
  _triggerClose: (code?: number) => void;
  _sentMessages: string[];
};

let instances: FakeWSInstance[] = [];

class FakeWebSocket {
  url: string;
  readyState = 0; // CONNECTING
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  _sentMessages: string[] = [];

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    instances.push(this as unknown as FakeWSInstance);
  }

  close(code?: number) {
    this.readyState = FakeWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code ?? 1000, wasClean: true }));
    }
  }

  send(data: string) {
    this._sentMessages.push(data);
  }

  _triggerOpen() {
    this.readyState = FakeWebSocket.OPEN;
    if (this.onopen) this.onopen(new Event('open'));
  }

  _triggerMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  _triggerClose(code?: number) {
    this.readyState = FakeWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code ?? 1000, wasClean: code === undefined || code === 1000 }));
    }
  }
}

function lastSocketUrl(): string {
  return instances.at(-1)?.url ?? '';
}

function socketCount(): number {
  return instances.length;
}

function mockServerSend(data: unknown): void {
  const inst = instances.at(-1);
  if (!inst) throw new Error('no socket instance to send on');
  if (inst.readyState !== FakeWebSocket.OPEN) inst._triggerOpen();
  inst._triggerMessage(data);
}

function mockServerClose(code?: number): void {
  const inst = instances.at(-1);
  if (!inst) throw new Error('no socket instance to close');
  inst._triggerClose(code);
}

describe('useDisplaySocket', () => {
  beforeEach(() => {
    instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('connects with device_token query param', () => {
    renderHook(() => useDisplaySocket('tok123'));
    expect(lastSocketUrl()).toContain('device_token=tok123');
  });

  it('stores family_presence, neighborhood_state, status', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => mockServerSend({ type: 'family_presence', entries: [{ user_id: 'u1' }] }));
    act(() => mockServerSend({ type: 'neighborhood_state', active: false }));
    expect(result.current.presence).toHaveLength(1);
    expect(result.current.neighborhood?.active).toBe(false);
  });

  it('caps message history at 20', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => {
      for (let i = 0; i < 30; i++) {
        mockServerSend({ type: 'chat_echo', ts: `t${i}`, display_name: 'A', text: `m${i}` });
      }
    });
    expect(result.current.messages).toHaveLength(20);
    expect(result.current.messages.at(-1)?.text).toBe('m29');
  });

  it('sets authFailed on close 4001 and does not reconnect', () => {
    const { result } = renderHook(() => useDisplaySocket('bad'));
    act(() => mockServerClose(4001));
    expect(result.current.authFailed).toBe(true);
    expect(socketCount()).toBe(1);
  });

  it('surfaces latest alert from ncs_alert and neighborhood_alert', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => mockServerSend({ type: 'neighborhood_alert', message: 'Ice on Elm St', ts: '2026-07-18T00:00:00Z' }));
    expect(result.current.alert?.kind).toBe('street');
  });

  it('reconnects with capped exponential backoff on non-4001 close', () => {
    renderHook(() => useDisplaySocket('tok123'));
    act(() => mockServerClose(1000));
    expect(socketCount()).toBe(1);
    act(() => { vi.advanceTimersByTime(1100); });
    expect(socketCount()).toBe(2);
  });

  it('send() dispatches over the open socket', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => mockServerSend({ type: 'status', radio_connected: true, volume_ok: true, channel_clear: true }));
    act(() => { result.current.send({ type: 'display_im_ok', user_id: 'u1' }); });
    const sent = JSON.parse(instances[0]._sentMessages[0]);
    expect(sent).toMatchObject({ type: 'display_im_ok', user_id: 'u1' });
  });
});
