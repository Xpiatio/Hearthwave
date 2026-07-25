import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
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
  _sentMessages: string[];
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

  _sentMessages: string[] = [];

  close(code?: number) {
    this.readyState = FakeWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code ?? 1000, wasClean: true }));
    }
  }

  send(data: string) {
    this._sentMessages.push(data);
  }
}

function mockServerClose(code?: number, reason = ''): void {
  const inst = instances.at(-1);
  if (!inst) throw new Error('no socket instance to close');
  inst.readyState = FakeWebSocket.CLOSED;
  if (inst.onclose) {
    inst.onclose(new CloseEvent('close', { code: code ?? 1000, reason, wasClean: code === 1000 }));
  }
}

function mockServerSend(payload: object): void {
  const inst = instances.at(-1);
  if (!inst) throw new Error('no socket instance to send to');
  // Flip to OPEN on first use so send() (which guards on readyState) can
  // actually forward client-originated messages in tests that check them.
  if (inst.readyState !== FakeWebSocket.OPEN) {
    inst.readyState = FakeWebSocket.OPEN;
    if (inst.onopen) inst.onopen(new Event('open'));
  }
  if (inst.onmessage) {
    inst.onmessage(new MessageEvent('message', { data: JSON.stringify(payload) }));
  }
}

// Returns the last payload the component sent over the socket (parsed), or
// null if nothing has been sent yet.
function lastSent(): unknown {
  const inst = instances.at(-1);
  const raw = inst?._sentMessages.at(-1);
  return raw ? JSON.parse(raw) : null;
}

let entrySeq = 0;
function okEntry(name: string, userId?: string): FamilyPresenceEntry {
  return {
    user_id: userId ?? `u-${++entrySeq}`,
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

  it('asks for a pairing code when nothing is stored', () => {
    render(<DisplayApp />);
    expect(screen.getByLabelText(/pairing code/i)).toBeInTheDocument();
  });

  it('offers the raw token field under an advanced toggle', () => {
    render(<DisplayApp />);
    expect(screen.queryByLabelText(/device token/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /paste a device token/i }));
    expect(screen.getByLabelText(/device token/i)).toBeInTheDocument();
  });

  it('stores the token and connects on submit', () => {
    render(<DisplayApp />);
    fireEvent.click(screen.getByRole('button', { name: /paste a device token/i }));
    fireEvent.change(screen.getByLabelText(/device token/i), { target: { value: 'tok123' } });
    fireEvent.click(screen.getByRole('button', { name: /^connect$/i }));
    expect(localStorage.getItem('radio_tty_device_token')).toBe('tok123');
  });

  it('exchanges a pairing code for a token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ token: 'tok-from-code' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<DisplayApp />);
    fireEvent.change(screen.getByLabelText(/pairing code/i), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: /pair this display/i }));
    await waitFor(() =>
      expect(localStorage.getItem('radio_tty_device_token')).toBe('tok-from-code'),
    );
    expect(fetchMock).toHaveBeenCalledWith('/display/pair', expect.objectContaining({ method: 'POST' }));
  });

  it('surfaces the server message when a pairing code is rejected', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'That code is not valid. Ask for a new one.' }),
    }));
    render(<DisplayApp />);
    fireEvent.change(screen.getByLabelText(/pairing code/i), { target: { value: '000000' } });
    fireEvent.click(screen.getByRole('button', { name: /pair this display/i }));
    expect(await screen.findByText(/code is not valid/i)).toBeInTheDocument();
    expect(localStorage.getItem('radio_tty_device_token')).toBeNull();
  });

  it('takes a token from ?token= and scrubs it from the URL', () => {
    window.history.replaceState(null, '', '/display?token=from-url');
    render(<DisplayApp />);
    expect(localStorage.getItem('radio_tty_device_token')).toBe('from-url');
    expect(window.location.search).toBe('');
    expect(screen.getByTestId('display-shell')).toBeInTheDocument();
  });

  it('shows the connected placeholder shell once a token is set', () => {
    localStorage.setItem('radio_tty_device_token', 'tok123');
    render(<DisplayApp />);
    expect(screen.getByTestId('display-shell')).toBeInTheDocument();
  });

  it('keeps the pairing on a reasonless 4001 instead of un-pairing', () => {
    localStorage.setItem('radio_tty_device_token', 'tok123');
    render(<DisplayApp />);
    act(() => mockServerClose(4001));
    expect(localStorage.getItem('radio_tty_device_token')).toBe('tok123');
    expect(screen.getByTestId('display-shell')).toBeInTheDocument();
  });

  it('warns but keeps the token when the server says it is invalid', () => {
    localStorage.setItem('radio_tty_device_token', 'bad');
    render(<DisplayApp />);
    act(() => mockServerClose(4001, 'device_token_invalid'));
    expect(screen.getByText(/no longer paired/i)).toBeInTheDocument();
    // The operator decides — the kiosk never drops its own pairing.
    expect(localStorage.getItem('radio_tty_device_token')).toBe('bad');
  });

  it('clears the token only when the operator taps Re-pair', () => {
    localStorage.setItem('radio_tty_device_token', 'bad');
    render(<DisplayApp />);
    act(() => mockServerClose(4001, 'device_token_invalid'));
    fireEvent.click(screen.getByRole('button', { name: /re-pair/i }));
    expect(localStorage.getItem('radio_tty_device_token')).toBeNull();
    expect(screen.getByLabelText(/pairing code/i)).toBeInTheDocument();
    expect(screen.getByText(/was unpaired/i)).toBeInTheDocument();
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

  it('streams rx partials and updates them in place, then settles on the final', () => {
    const rx = (text: string, partial: boolean) => ({
      type: 'rx_message',
      utterance_id: 'u9',
      text,
      partial,
      callsign_spans: [],
      source: 'voice',
    });
    render(<DisplayApp />);
    act(() => mockServerSend(rx('This is', true)));
    expect(screen.getByText('This is')).toBeInTheDocument();
    // Next delta replaces the same line rather than adding a second one.
    act(() => mockServerSend(rx('This is the Inky', true)));
    expect(screen.queryByText('This is')).not.toBeInTheDocument();
    expect(screen.getByText('This is the Inky')).toBeInTheDocument();
    // Final settles the line — still exactly one entry for the utterance.
    act(() => mockServerSend(rx('This is the Inky Planner.', false)));
    expect(screen.getAllByText(/inky planner/i)).toHaveLength(1);
  });

  it('shows system messages from the radio stream', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'system_msg', text: 'Repeater timeout' }));
    expect(screen.getByText('Repeater timeout')).toBeInTheDocument();
  });

  it('keeps stream messages in the scrollable log', () => {
    render(<DisplayApp />);
    act(() => {
      for (let i = 0; i < 7; i++) mockServerSend(chatMsg(`msg ${i}`));
    });
    expect(screen.getByText('msg 1')).toBeInTheDocument();
    expect(screen.getByText('msg 6')).toBeInTheDocument();
  });

  it('applies the tile order stored on the device token', () => {
    render(<DisplayApp />);
    act(() => {
      mockServerSend({ type: 'display_config', eink: false, order: ['u3', 'u1'] });
      mockServerSend({
        type: 'family_presence',
        entries: [okEntry('Grandma', 'u1'), okEntry('Ben', 'u2'), okEntry('Mai', 'u3')],
      });
    });
    const names = screen.getAllByRole('listitem').map((el) => el.textContent);
    // Stored order first, then anyone the order has never seen.
    expect(names[0]).toContain('Mai');
    expect(names[1]).toContain('Grandma');
    expect(names[2]).toContain('Ben');
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

describe('DisplayApp wake interaction', () => {
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

  function renderAwake() {
    const rendered = render(<DisplayApp />);
    act(() => {
      mockServerSend({ type: 'status', display_quick_messages: ['Dinner is ready'] });
      mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma', 'u1')] });
    });
    fireEvent.click(screen.getByTestId('display-shell'));
    return rendered;
  }

  it('tap wakes interactive mode; quick messages appear', () => {
    renderAwake();
    expect(screen.getByRole('button', { name: 'Dinner is ready' })).toBeInTheDocument();
  });

  it('reverts to passive after 45s idle', () => {
    renderAwake();
    act(() => vi.advanceTimersByTime(45_000));
    expect(screen.queryByRole('button', { name: 'Dinner is ready' })).not.toBeInTheDocument();
  });

  it('tile tap opens confirm; Yes sends display_im_ok', () => {
    renderAwake();
    fireEvent.click(screen.getByRole('button', { name: /grandma/i }));
    fireEvent.click(screen.getByRole('button', { name: /yes/i }));
    expect(lastSent()).toEqual({ type: 'display_im_ok', user_id: 'u1' });
  });

  it('confirm No sends nothing', () => {
    renderAwake();
    fireEvent.click(screen.getByRole('button', { name: /grandma/i }));
    fireEvent.click(screen.getByRole('button', { name: /no/i }));
    expect(lastSent()).toBeNull();
  });

  it('quick message tap sends display_quick_message and shows Sent on ack', () => {
    renderAwake();
    fireEvent.click(screen.getByRole('button', { name: 'Dinner is ready' }));
    expect(lastSent()).toEqual({ type: 'display_quick_message', text: 'Dinner is ready' });
    act(() => mockServerSend({ type: 'display_ack', action: 'quick_message' }));
    expect(screen.getByText(/sent/i)).toBeInTheDocument();
  });

  // The drag itself needs real layout, which jsdom has not — the reordering
  // maths is covered by display/tileOrder.test.ts, and a real drag is on the
  // manual checklist. What is worth asserting here is that the tiles become
  // draggable at all, and only while awake.
  it('makes tiles sortable once awake, and not before', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma', 'u1')] }));
    expect(screen.getByRole('listitem')).not.toHaveAttribute('aria-roledescription', 'sortable');

    fireEvent.click(screen.getByTestId('display-shell'));
    expect(screen.getByRole('listitem')).toHaveAttribute('aria-roledescription', 'sortable');
  });

  it('leaves e-ink panels un-draggable — movement smears the panel', () => {
    render(<DisplayApp />);
    act(() => {
      mockServerSend({ type: 'display_config', eink: true, order: [] });
      mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma', 'u1')] });
    });
    fireEvent.click(screen.getByTestId('display-shell'));
    expect(screen.getByRole('listitem')).not.toHaveAttribute('aria-roledescription', 'sortable');
  });

  it('interactive mode passes axe', async () => {
    const { container } = renderAwake();
    // jest-axe's internal async work relies on real timers; fake timers
    // (set up in beforeEach for the 45s wake-window assertions) would hang it.
    vi.useRealTimers();
    expect(await axe(container)).toHaveNoViolations();
  });
});
