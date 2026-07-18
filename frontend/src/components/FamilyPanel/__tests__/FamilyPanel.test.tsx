import { render as rtlRender, screen, fireEvent, within } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { FamilyPanel } from '../FamilyPanel';
import type { FamilyPanelProps } from '../FamilyPanel';
import type { FamilyPresenceEntry } from '../../../types/ws';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

const entries: FamilyPresenceEntry[] = [
  {
    user_id: 'u1',
    display_name: 'U1',
    avatar_emoji: '🙂',
    last_heard: null,
    last_ok: new Date().toISOString(),
    missed_checkin: false,
  },
  {
    user_id: 'u2',
    display_name: 'U2',
    avatar_emoji: '🧒',
    last_heard: null,
    last_ok: null,
    missed_checkin: true,
  },
];

function makeProps(overrides: Partial<FamilyPanelProps> = {}): FamilyPanelProps {
  return {
    entries,
    reminders: { u2: { time: '08:00', enabled: true } },
    isKid: false,
    isAdmin: true,
    quickMessages: ['I love you', 'Heading home'],
    onImOk: vi.fn(),
    onQuickMessage: vi.fn(),
    onSetReminder: vi.fn(),
    onGoHome: vi.fn(),
    ...overrides,
  };
}

describe('FamilyPanel', () => {
  it('renders a member card per entry with status text', () => {
    render(<FamilyPanel {...makeProps()} />);
    const board = screen.getByRole('list', { name: 'Family members' });
    const items = within(board).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText(/OK/)).toBeInTheDocument();
    expect(within(items[1]).getByText('Missed check-in')).toBeInTheDocument();
  });

  it("giant I'm OK button fires onImOk", () => {
    const props = makeProps();
    render(<FamilyPanel {...props} />);
    fireEvent.click(screen.getByRole('button', { name: "I'm OK" }));
    expect(props.onImOk).toHaveBeenCalledOnce();
  });

  it('quick messages fire onQuickMessage with preset text', () => {
    const props = makeProps();
    render(<FamilyPanel {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Heading home' }));
    expect(props.onQuickMessage).toHaveBeenCalledWith('Heading home');
  });

  it('reminder editor hidden for non-admin, saves for admin', () => {
    const nonAdmin = makeProps({ isAdmin: false });
    const { unmount } = render(<FamilyPanel {...nonAdmin} />);
    expect(screen.queryByLabelText(/Check-in reminder/)).not.toBeInTheDocument();
    unmount();

    const admin = makeProps();
    render(<FamilyPanel {...admin} />);
    fireEvent.change(screen.getByLabelText('Check-in reminder for U2'), { target: { value: '09:00' } });
    expect(admin.onSetReminder).toHaveBeenCalledWith('u2', '09:00', true);
  });

  it('normalizes an emptied time field to null rather than an empty string', () => {
    const props = makeProps();
    render(<FamilyPanel {...props} />);
    fireEvent.change(screen.getByLabelText('Check-in reminder for U2'), { target: { value: '' } });
    expect(props.onSetReminder).toHaveBeenCalledWith('u2', null, true);
  });

  it("kid mode hides reminder editor and shows only I'm OK + quick messages", () => {
    render(<FamilyPanel {...makeProps({ isKid: true, isAdmin: false })} />);
    expect(screen.getByRole('button', { name: "I'm OK" })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Heading home' })).toBeInTheDocument();
    expect(screen.queryByLabelText(/Check-in reminder/)).not.toBeInTheDocument();
  });

  it('kid with an empty preset list gets an explanatory empty state instead of a dead row', () => {
    render(<FamilyPanel {...makeProps({ isKid: true, isAdmin: false, quickMessages: [] })} />);
    expect(screen.getByText('Ask an adult to set up your messages.')).toBeInTheDocument();
  });

  it('adult with an empty preset list still gets the (empty) button row, not the kid empty state', () => {
    render(<FamilyPanel {...makeProps({ isKid: false, quickMessages: [] })} />);
    expect(screen.queryByText('Ask an adult to set up your messages.')).not.toBeInTheDocument();
  });

  it('back button returns home', () => {
    const props = makeProps();
    render(<FamilyPanel {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Back to home' }));
    expect(props.onGoHome).toHaveBeenCalledOnce();
  });

  it('has no axe violations', async () => {
    const { container } = render(<FamilyPanel {...makeProps()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
