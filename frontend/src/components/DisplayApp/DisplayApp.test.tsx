import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { axe } from 'jest-axe';
import { DisplayApp } from './DisplayApp';
import type { FamilyPresenceEntry } from '../../types/ws';

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

function mockServerSend(payload: object): void {
  const inst = instances.at(-1);
  if (!inst) throw new Error('no socket instance to send to');
  if (inst.onmessage) {
    inst.onmessage(new MessageEvent('message', { data: JSON.stringify(payload) }));
  }
}

let entrySeq = 0;
function okEntry(name: string): FamilyPresenceEntry {
  return {
    user_id: `u-${++entrySeq}`,
    display_name: name,
    avatar_emoji: '🙂',
    last_heard: null,
    last_ok: new Date().toISOString(),
    missed_checkin: false,
  };
}

function noWordEntry(name: string): FamilyPresenceEntry {
  return {
    user_id: `u-${++entrySeq}`,
    display_name: name,
    avatar_emoji: '🧒',
    last_heard: null,
    last_ok: null,
    missed_checkin: false,
  };
}

function chatMsg(text: string) {
  return {
    type: 'chat_echo',
    ts: new Date().toISOString(),
    display_name: 'Tester',
    operator: 'tester',
    callsign: 'W1AW',
    text,
  };
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

describe('DisplayApp passive layout', () => {
  beforeEach(() => {
    localStorage.clear();
    instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    localStorage.setItem('radio_tty_device_token', 'tok123');
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders a presence tile per family member with status', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma'), noWordEntry('Ben')] }));
    expect(screen.getByText('Grandma')).toBeInTheDocument();
    expect(screen.getByText(/ok/i)).toBeInTheDocument();
  });

  it('shows the latest 3 chat messages only', () => {
    render(<DisplayApp />);
    act(() => {
      for (let i = 0; i < 5; i++) mockServerSend(chatMsg(`msg ${i}`));
    });
    expect(screen.queryByText('msg 1')).not.toBeInTheDocument();
    expect(screen.getByText('msg 4')).toBeInTheDocument();
  });

  it('shows street alert banner when one arrives', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'neighborhood_alert', id: 'a1', message: 'Ice on Elm St', issued_by: 'admin', ts: new Date().toISOString() }));
    expect(screen.getByRole('alert')).toHaveTextContent('Ice on Elm St');
  });

  it('shows next net from neighborhood_state schedule', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'neighborhood_state', active: false, net_day: 'Tuesday', net_time: '19:00', roster: [], current_call: null }));
    expect(screen.getByText(/net tue/i)).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = render(<DisplayApp />);
    act(() => mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma')] }));
    // jest-axe's internal async work relies on real timers; fake timers
    // (set up in beforeEach for the clock/drift assertions) would hang it.
    vi.useRealTimers();
    expect(await axe(container)).toHaveNoViolations();
  });
});
