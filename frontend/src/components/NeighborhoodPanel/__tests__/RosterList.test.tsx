import { render as rtlRender, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { RosterList } from '../RosterList';
import type { RosterListProps } from '../RosterList';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

const accountRow = {
  user_id: 'u1', callsign: 'WRAA111', name: 'Ann', location: '1st St',
  status: 'checked_in' as const, checkin_time: '2026-08-01T19:30:00Z', called: false,
};
const radioRow = {
  user_id: 'radio:WRAB123:maria', callsign: 'WRAB123', name: 'Maria',
  location: 'Maple St', status: 'checked_in' as const,
  checkin_time: '2026-08-01T19:31:00Z', called: false, via: 'radio' as const,
};

function makeProps(overrides: Partial<RosterListProps> = {}): RosterListProps {
  return {
    roster: [],
    currentCall: null,
    myUserId: 'u1',
    onStatusChange: vi.fn(),
    ...overrides,
  };
}

describe('RosterList', () => {
  it('marks radio rows and only radio rows', () => {
    render(<RosterList {...makeProps({ roster: [accountRow, radioRow] })} />);
    expect(screen.getAllByText('By radio')).toHaveLength(1);
  });

  it('gives a coordinator a status control on a radio row', async () => {
    const user = userEvent.setup();
    const onStationStatusChange = vi.fn();
    render(
      <RosterList
        {...makeProps({ roster: [radioRow], isCoordinator: true, onStationStatusChange })}
      />
    );
    await user.click(screen.getByRole('button', { name: 'Standby' }));
    expect(onStationStatusChange).toHaveBeenCalledWith('radio:WRAB123:maria', 'standby');
  });

  it('cycles a radio row through third-person labels', async () => {
    const user = userEvent.setup();
    const onStationStatusChange = vi.fn();
    const standbyRow = { ...radioRow, status: 'standby' as const };
    const { rerender } = render(
      <RosterList
        {...makeProps({ roster: [standbyRow], isCoordinator: true, onStationStatusChange })}
      />
    );
    expect(screen.getByRole('button', { name: 'Check out' })).toBeInTheDocument();

    const checkedOutRow = { ...radioRow, status: 'checked_out' as const };
    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <RosterList
          {...makeProps({ roster: [checkedOutRow], isCoordinator: true, onStationStatusChange })}
        />
      </ThemeProvider>
    );
    await user.click(screen.getByRole('button', { name: 'Check back in' }));
    expect(onStationStatusChange).toHaveBeenCalledWith('radio:WRAB123:maria', 'checked_in');
  });

  it('keeps first-person labels on the viewer own row', async () => {
    const user = userEvent.setup();
    const onStatusChange = vi.fn();
    const onStationStatusChange = vi.fn();
    render(
      <RosterList
        {...makeProps({
          roster: [accountRow],
          isCoordinator: true,
          onStatusChange,
          onStationStatusChange,
        })}
      />
    );
    const button = screen.getByRole('button', { name: 'Step away' });
    await user.click(button);
    expect(onStatusChange).toHaveBeenCalledWith('standby');
    expect(onStationStatusChange).not.toHaveBeenCalled();
  });

  it('shows no radio controls to a non-coordinator', () => {
    render(<RosterList {...makeProps({ roster: [radioRow], isCoordinator: false })} />);
    expect(screen.queryByRole('button', { name: 'Standby' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument();
  });

  it('does not offer remove on an account row', () => {
    render(
      <RosterList
        {...makeProps({
          roster: [accountRow, radioRow],
          isCoordinator: true,
          onRemoveStation: vi.fn(),
        })}
      />
    );
    expect(screen.getAllByRole('button', { name: 'Remove Maria' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Remove Ann' })).not.toBeInTheDocument();
  });

  it('removes a radio row without a confirmation step', async () => {
    const user = userEvent.setup();
    const onRemoveStation = vi.fn();
    render(
      <RosterList
        {...makeProps({ roster: [radioRow], isCoordinator: true, onRemoveStation })}
      />
    );
    await user.click(screen.getByRole('button', { name: 'Remove Maria' }));
    expect(onRemoveStation).toHaveBeenCalledWith('radio:WRAB123:maria');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('has no axe violations with radio-row controls shown', async () => {
    const { container } = render(
      <RosterList
        {...makeProps({
          roster: [accountRow, radioRow],
          isCoordinator: true,
          onStationStatusChange: vi.fn(),
          onRemoveStation: vi.fn(),
        })}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
