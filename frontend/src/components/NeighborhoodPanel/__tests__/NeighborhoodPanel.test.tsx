import { render as rtlRender, screen, fireEvent, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { NeighborhoodPanel } from '../NeighborhoodPanel';
import type { NeighborhoodPanelProps } from '../NeighborhoodPanel';
import type { IncidentEntry, NeighborhoodAlertMsg, NeighborhoodRosterRow } from '../../../types/ws';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

const roster: NeighborhoodRosterRow[] = [
  {
    user_id: 'u1', callsign: 'W1ABC', name: 'Alice', location: 'Elm St',
    status: 'checked_in', checkin_time: new Date().toISOString(), called: false,
  },
  {
    user_id: 'u3', callsign: 'W2XYZ', name: 'Bob', location: 'Oak Ave',
    status: 'standby', checkin_time: new Date().toISOString(), called: true,
  },
];

const incidents: IncidentEntry[] = [
  { id: 'i1', category: 'hazard', description: 'Tree down', location: 'Elm & Main', reporter: 'Alice', ts: new Date(Date.now() - 60_000).toISOString() },
  { id: 'i2', category: 'lost', description: 'Missing cat, brown collar', location: 'Oak St', reporter: 'Bob', ts: new Date().toISOString() },
];

const alerts: NeighborhoodAlertMsg[] = [
  { type: 'neighborhood_alert', id: 'a1', message: 'Boil water advisory', issued_by: 'Coordinator', ts: new Date().toISOString() },
];

function makeProps(overrides: Partial<NeighborhoodPanelProps> = {}): NeighborhoodPanelProps {
  return {
    roster,
    netActive: false,
    currentCall: null,
    incidents,
    alerts,
    netDay: 'tue',
    netTime: '19:00',
    isCoordinator: false,
    isKid: false,
    myUserId: 'u2',
    onCheckin: vi.fn(),
    onStatusChange: vi.fn(),
    onIncidentReport: vi.fn(),
    incidentError: null,
    onStreetAlert: vi.fn(),
    onStartNet: vi.fn(),
    onEndNet: vi.fn(),
    onCallNext: vi.fn(),
    onNewRound: vi.fn(),
    onGoHome: vi.fn(),
    ...overrides,
  };
}

describe('NeighborhoodPanel', () => {
  it('renders header with title, net chip, and next-net label when inactive', () => {
    render(<NeighborhoodPanel {...makeProps()} />);
    expect(screen.getByText('Neighborhood')).toBeInTheDocument();
    expect(screen.getByText('No net right now')).toBeInTheDocument();
    expect(screen.getByText(/Net Tue 7:00 PM/)).toBeInTheDocument();
  });

  it('shows "Net running" and hides the next-net label when active', () => {
    render(<NeighborhoodPanel {...makeProps({ netActive: true })} />);
    expect(screen.getByText('Net running')).toBeInTheDocument();
    expect(screen.queryByText(/Net Tue 7:00 PM/)).not.toBeInTheDocument();
  });

  it('back button returns home', () => {
    const props = makeProps();
    render(<NeighborhoodPanel {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Back to home' }));
    expect(props.onGoHome).toHaveBeenCalledOnce();
  });

  it('check-in button fires onCheckin when not yet in the roster', () => {
    const props = makeProps({ myUserId: 'someone-else' });
    render(<NeighborhoodPanel {...props} />);
    const btn = screen.getByRole('button', { name: 'Check in' });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(props.onCheckin).toHaveBeenCalledOnce();
  });

  it('check-in button flips to disabled confirmation once own user_id is in the roster', () => {
    render(<NeighborhoodPanel {...makeProps({ myUserId: 'u1' })} />);
    const btn = screen.getByRole('button', { name: "You're checked in ✓" });
    expect(btn).toBeDisabled();
  });

  it('shows the alert banner with message text', () => {
    render(<NeighborhoodPanel {...makeProps()} />);
    expect(screen.getByText(/Boil water advisory/)).toBeInTheDocument();
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0);
  });

  it('renders no alert banner when there are no alerts', () => {
    render(<NeighborhoodPanel {...makeProps({ alerts: [] })} />);
    expect(screen.queryByText(/Boil water advisory/)).not.toBeInTheDocument();
  });

  it('hides the "Report an incident" button for kid accounts', () => {
    render(<NeighborhoodPanel {...makeProps({ isKid: true })} />);
    expect(screen.queryByRole('button', { name: 'Report an incident' })).not.toBeInTheDocument();
  });

  it('report-an-incident flow: opens dialog, gates submit until valid, sends the expected payload, and closes', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<NeighborhoodPanel {...props} />);

    await user.click(screen.getByRole('button', { name: 'Report an incident' }));
    const dialog = screen.getByRole('dialog');
    const submit = within(dialog).getByRole('button', { name: 'Send report' });
    expect(submit).toBeDisabled();

    await user.click(within(dialog).getByRole('combobox', { name: 'Category' }));
    await user.click(await screen.findByRole('option', { name: 'Medical' }));

    await user.type(within(dialog).getByLabelText(/what happened/i), 'Neighbor fell, needs help');
    expect(submit).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/location/i), '12 Oak St');
    expect(submit).not.toBeDisabled();

    await user.click(submit);
    expect(props.onIncidentReport).toHaveBeenCalledWith({
      category: 'medical',
      description: 'Neighbor fell, needs help',
      location: '12 Oak St',
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('reopens the incident dialog to surface a server-side incidentError', () => {
    const props = makeProps();
    const { rerender } = render(<NeighborhoodPanel {...props} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <NeighborhoodPanel {...props} incidentError="Description is required." />
      </ThemeProvider>,
    );
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Description is required.')).toBeInTheDocument();
  });

  it('does not auto-open the incident dialog for a stale incidentError already set at mount', () => {
    const props = makeProps({ incidentError: 'Description is required.' });
    render(<NeighborhoodPanel {...props} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('does not show stale error text when the dialog is reopened manually after being dismissed', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    const { rerender } = render(<NeighborhoodPanel {...props} />);

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <NeighborhoodPanel {...props} incidentError="Description is required." />
      </ThemeProvider>,
    );
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Description is required.')).toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // incidentError prop is still the stale value from App.tsx's perspective
    // (nothing cleared it) — reopening manually must not resurface it.
    await user.click(screen.getByRole('button', { name: 'Report an incident' }));
    const reopened = screen.getByRole('dialog');
    expect(within(reopened).queryByText('Description is required.')).not.toBeInTheDocument();
  });

  it('incident log filter narrows the newest-first list to the selected category', async () => {
    const user = userEvent.setup();
    render(<NeighborhoodPanel {...makeProps()} />);

    const list = screen.getByRole('list', { name: 'Incident reports' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);

    await user.click(screen.getByRole('combobox', { name: 'Filter by category' }));
    await user.click(await screen.findByRole('option', { name: 'Lost pet or person' }));

    const filtered = within(screen.getByRole('list', { name: 'Incident reports' })).getAllByRole('listitem');
    expect(filtered).toHaveLength(1);
    expect(within(filtered[0]).getByText('Missing cat, brown collar')).toBeInTheDocument();
  });

  it('hides the coordinator section for a non-coordinator', () => {
    render(<NeighborhoodPanel {...makeProps({ isCoordinator: false })} />);
    expect(screen.queryByText('Coordinator tools')).not.toBeInTheDocument();
  });

  it('hides the coordinator section for a kid even if flagged as coordinator', () => {
    render(<NeighborhoodPanel {...makeProps({ isCoordinator: true, isKid: true })} />);
    expect(screen.queryByText('Coordinator tools')).not.toBeInTheDocument();
  });

  it('coordinator section: Start/End net toggles, Call next / New round fire callbacks', () => {
    const props = makeProps({ isCoordinator: true, netActive: false });
    const { rerender } = render(<NeighborhoodPanel {...props} />);

    const startBtn = screen.getByRole('button', { name: 'Start net' });
    fireEvent.click(startBtn);
    expect(props.onStartNet).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Call next neighbor' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'New round' })).toBeDisabled();

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <NeighborhoodPanel {...props} netActive />
      </ThemeProvider>,
    );
    const endBtn = screen.getByRole('button', { name: 'End net' });
    fireEvent.click(endBtn);
    expect(props.onEndNet).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole('button', { name: 'Call next neighbor' }));
    expect(props.onCallNext).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'New round' }));
    expect(props.onNewRound).toHaveBeenCalledOnce();
  });

  it('shows the current round-table call in the coordinator section, resolved to a display name', () => {
    // I2: the backend sends current_call as a user_id (see
    // backend/neighborhood/net.py's call_next), never a callsign — this
    // must resolve through the roster, not render the raw id.
    render(<NeighborhoodPanel {...makeProps({ isCoordinator: true, currentCall: 'u1' })} />);
    expect(screen.getByText('Current turn: Alice')).toBeInTheDocument();
    expect(screen.queryByText(/u1/)).not.toBeInTheDocument();
  });

  it('falls back to callsign, then to nothing, when resolving current_call to a display name', () => {
    const noNameRoster: NeighborhoodRosterRow[] = [
      { user_id: 'u9', callsign: 'W9NAM', name: '', location: 'Pine St', status: 'checked_in', checkin_time: new Date().toISOString(), called: false },
    ];
    const { rerender } = render(
      <NeighborhoodPanel {...makeProps({ isCoordinator: true, roster: noNameRoster, currentCall: 'u9' })} />,
    );
    expect(screen.getByText('Current turn: W9NAM')).toBeInTheDocument();

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <NeighborhoodPanel {...makeProps({ isCoordinator: true, roster: [], currentCall: 'unknown-user' })} />
      </ThemeProvider>,
    );
    expect(screen.getByText('Current turn:')).toBeInTheDocument();
    expect(screen.queryByText(/unknown-user/)).not.toBeInTheDocument();
  });

  describe('street alert', () => {
    it('sends the alert after confirming', () => {
      const props = makeProps({ isCoordinator: true });
      render(<NeighborhoodPanel {...props} />);

      fireEvent.change(screen.getByLabelText('Street alert message'), { target: { value: 'Power out on Maple St' } });
      fireEvent.click(screen.getByRole('button', { name: 'Send street alert' }));

      expect(props.onStreetAlert).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: /yes, send the alert/i }));
      expect(props.onStreetAlert).toHaveBeenCalledWith('Power out on Maple St');
    });

    it('does not send when the confirmation is declined', () => {
      const props = makeProps({ isCoordinator: true });
      render(<NeighborhoodPanel {...props} />);

      fireEvent.change(screen.getByLabelText('Street alert message'), { target: { value: 'Power out on Maple St' } });
      fireEvent.click(screen.getByRole('button', { name: 'Send street alert' }));
      fireEvent.click(screen.getByRole('button', { name: /no, go back/i }));

      expect(props.onStreetAlert).not.toHaveBeenCalled();
    });
  });

  describe('roster list', () => {
    it('renders a row per roster entry with name, callsign, location, and status', () => {
      render(<NeighborhoodPanel {...makeProps()} />);
      const list = screen.getByRole('list', { name: 'Checked-in neighbors' });
      const rows = within(list).getAllByRole('listitem');
      expect(rows).toHaveLength(2);

      expect(within(rows[0]).getByText('Alice')).toBeInTheDocument();
      expect(within(rows[0]).getByText('W1ABC')).toBeInTheDocument();
      expect(within(rows[0]).getByText('Elm St')).toBeInTheDocument();
      expect(within(rows[0]).getByText('Checked in')).toBeInTheDocument();

      expect(within(rows[1]).getByText('Bob')).toBeInTheDocument();
      expect(within(rows[1]).getByText('W2XYZ')).toBeInTheDocument();
      expect(within(rows[1]).getByText('Oak Ave')).toBeInTheDocument();
      expect(within(rows[1]).getByText('Standby')).toBeInTheDocument();
    });

    it('marks a called row with a "Called ✓" label', () => {
      render(<NeighborhoodPanel {...makeProps()} />);
      const list = screen.getByRole('list', { name: 'Checked-in neighbors' });
      const rows = within(list).getAllByRole('listitem');
      expect(within(rows[0]).queryByText('Called ✓')).not.toBeInTheDocument();
      expect(within(rows[1]).getByText('Called ✓')).toBeInTheDocument();
    });

    it('highlights the current_call row with a text "Current turn" label', () => {
      render(<NeighborhoodPanel {...makeProps({ currentCall: 'u1' })} />);
      const list = screen.getByRole('list', { name: 'Checked-in neighbors' });
      const rows = within(list).getAllByRole('listitem');
      expect(within(rows[0]).getByText('Current turn')).toBeInTheDocument();
      expect(within(rows[1]).queryByText('Current turn')).not.toBeInTheDocument();
    });

    it('shows "No one checked in yet." when the roster is empty', () => {
      render(<NeighborhoodPanel {...makeProps({ roster: [] })} />);
      expect(screen.getByText('No one checked in yet.')).toBeInTheDocument();
      expect(screen.queryByRole('list', { name: 'Checked-in neighbors' })).not.toBeInTheDocument();
    });

    it('shows a self-toggle button only on the viewer\'s own row, and it fires onStatusChange', () => {
      const props = makeProps({ myUserId: 'u1' });
      render(<NeighborhoodPanel {...props} />);
      const list = screen.getByRole('list', { name: 'Checked-in neighbors' });
      const rows = within(list).getAllByRole('listitem');

      // Own row (u1, checked_in): a "Step away" button, toggling to standby.
      const stepAway = within(rows[0]).getByRole('button', { name: 'Step away' });
      fireEvent.click(stepAway);
      expect(props.onStatusChange).toHaveBeenCalledWith('standby');

      // Other row (u3, standby): no self-toggle button at all.
      expect(within(rows[1]).queryByRole('button')).not.toBeInTheDocument();
    });

    it('shows "I\'m back" on the viewer\'s own row when currently on standby', () => {
      const props = makeProps({ myUserId: 'u3' });
      render(<NeighborhoodPanel {...props} />);
      const list = screen.getByRole('list', { name: 'Checked-in neighbors' });
      const rows = within(list).getAllByRole('listitem');

      const imBack = within(rows[1]).getByRole('button', { name: "I'm back" });
      fireEvent.click(imBack);
      expect(props.onStatusChange).toHaveBeenCalledWith('checked_in');
      expect(within(rows[0]).queryByRole('button')).not.toBeInTheDocument();
    });
  });

  it('has no axe violations in the base state or with the incident dialog open', async () => {
    const { container } = render(<NeighborhoodPanel {...makeProps()} />);
    expect(await axe(container)).toHaveNoViolations();

    fireEvent.click(screen.getByRole('button', { name: 'Report an incident' }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
