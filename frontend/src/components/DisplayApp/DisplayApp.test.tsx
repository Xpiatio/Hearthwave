import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { DisplayApp } from './DisplayApp';

// ---------------------------------------------------------------------------
// Fake WebSocket implementation (mirrors src/hooks/__tests__/useWebSocket.test.ts
// and src/hooks/useDisplaySocket.test.ts)
// ---------------------------------------------------------------------------

type FakeWSInstance = {
  url: string;
  readyState: number;
  onopen: ((e: Event) => void) | null;
  onmessage: ((e: MessageEvent) => void) | null;
  onclose: ((e: CloseEvent) => void) | null;
  onerror: ((e: Event) => void) | null;
  close: (code?: number) => void;
  send: (data: string) => void;
};

let instances: FakeWSInstance[] = [];

class FakeWebSocket {
  url: string;
  readyState = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

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

  send() {
    // no-op for these tests
  }
}

function mockServerClose(code?: number): void {
  const inst = instances.at(-1);
  if (!inst) throw new Error('no socket instance to close');
  inst.readyState = FakeWebSocket.CLOSED;
  if (inst.onclose) {
    inst.onclose(new CloseEvent('close', { code: code ?? 1000, wasClean: code === 1000 }));
  }
}

describe('DisplayApp token entry', () => {
  beforeEach(() => {
    localStorage.clear();
    instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('asks for a device token when none stored', () => {
    render(<DisplayApp />);
    expect(screen.getByLabelText(/device token/i)).toBeInTheDocument();
  });

  it('stores the token and connects on submit', () => {
    render(<DisplayApp />);
    fireEvent.change(screen.getByLabelText(/device token/i), { target: { value: 'tok123' } });
    fireEvent.click(screen.getByRole('button', { name: /connect/i }));
    expect(localStorage.getItem('radio_tty_device_token')).toBe('tok123');
  });

  it('shows the connected placeholder shell once a token is set', () => {
    localStorage.setItem('radio_tty_device_token', 'tok123');
    render(<DisplayApp />);
    expect(screen.getByTestId('display-shell')).toBeInTheDocument();
  });

  it('shows error and re-shows entry after auth failure', () => {
    localStorage.setItem('radio_tty_device_token', 'bad');
    render(<DisplayApp />);
    act(() => mockServerClose(4001));
    expect(screen.getByText(/token was not accepted/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/device token/i)).toBeInTheDocument();
    expect(localStorage.getItem('radio_tty_device_token')).toBeNull();
  });
});
