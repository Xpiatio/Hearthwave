import { render as rtlRender, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { CoordinatorDashboard } from '../CoordinatorDashboard';
import type { CoordinatorDashboardProps } from '../CoordinatorDashboard';

// jsdom doesn't implement scrollIntoView — ChatDisplay calls it on mount.
window.HTMLElement.prototype.scrollIntoView = vi.fn();

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

function makeDashProps(overrides: Partial<CoordinatorDashboardProps> = {}): CoordinatorDashboardProps {
  return {
    roster: [], netActive: true, currentCall: null, incidents: [], alerts: [],
    netDay: 'Saturday', netTime: '09:00', isCoordinator: true, isAdmin: false,
    isKid: false, myUserId: 'u1',
    onCheckin: vi.fn(), onClearCheckins: vi.fn(), onClearIncidents: vi.fn(),
    onStatusChange: vi.fn(), onIncidentReport: vi.fn(), incidentError: null,
    onStreetAlert: vi.fn(), onStartNet: vi.fn(), onEndNet: vi.fn(),
    onCallNext: vi.fn(), onNewRound: vi.fn(), onGoHome: vi.fn(),
    contacts: [], onRadioCheckin: vi.fn(), onStationStatusChange: vi.fn(),
    onRemoveStation: vi.fn(), onNoAnswer: vi.fn(), onCallStation: vi.fn(),
    messages: [], transmitting: false, showCallsignChips: false,
    onSendMessage: vi.fn(), onChat: vi.fn(), onStandaloneId: vi.fn(),
    txComposition: null,
    ...overrides,
  };
}

describe('CoordinatorDashboard', () => {
  it('renders every ops zone on one screen', () => {
    render(<CoordinatorDashboard {...makeDashProps()} />);
    expect(screen.getByRole('button', { name: 'End net' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Call next neighbor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New round' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Street alert…' })).toBeInTheDocument();
    expect(screen.getByText('Checked-in neighbors')).toBeInTheDocument();   // RosterList
    expect(screen.getByText('Incident log')).toBeInTheDocument();           // IncidentLog
    expect(screen.getByLabelText('Callsign')).toBeInTheDocument();          // RadioCheckinForm
    expect(screen.getByRole('button', { name: 'Report an incident' })).toBeInTheDocument();
  });

  it('opens the street-alert dialog and sends through the existing confirm flow', async () => {
    const user = userEvent.setup();
    const onStreetAlert = vi.fn();
    render(<CoordinatorDashboard {...makeDashProps({ onStreetAlert })} />);
    await user.click(screen.getByRole('button', { name: 'Street alert…' }));
    await user.type(screen.getByLabelText('Street alert message'), 'Power out on Maple St');
    await user.click(screen.getByRole('button', { name: 'Send street alert' }));
    // ConfirmDialog prefixes its confirm button with an emoji (see
    // ConfirmDialog.tsx and NeighborhoodPanel.test.tsx's street-alert test),
    // so match by substring rather than the exact label.
    await user.click(screen.getByRole('button', { name: /yes, send the alert/i }));
    expect(onStreetAlert).toHaveBeenCalledWith('Power out on Maple St');
  });

  it('shows a compact self check-in chip, not the billboard button', async () => {
    const user = userEvent.setup();
    const onCheckin = vi.fn();
    render(<CoordinatorDashboard {...makeDashProps({ onCheckin })} />);
    await user.click(screen.getByRole('button', { name: 'Check in' }));
    expect(onCheckin).toHaveBeenCalled();
  });

  it('transmits from the dashboard message input', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    render(<CoordinatorDashboard {...makeDashProps({ onSendMessage })} />);
    // MessageInput only sends on Ctrl/Meta+Enter or the send button (plain
    // Enter is a no-op — see MessageInput.test.tsx "does NOT send on plain
    // Enter"), so this drives the actual send button rather than Enter.
    const box = screen.getByRole('textbox', { name: /message text/i });
    await user.type(box, 'net control standing by');
    await user.click(screen.getByRole('button', { name: /press to send message/i }));
    expect(onSendMessage).toHaveBeenCalledWith('net control standing by', 'ALL', '');
  });
});
