import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { HomeScreen } from '../HomeScreen';
import type { FamilyPresenceEntry, UserProfile } from '../../../types/ws';

const profile = {
  id: 'u1', display_name: 'Ann', avatar_emoji: '🙂', operator_name: 'Ann',
  callsign: 'WABC123', location: 'Home', is_admin: false, role: 'adult', prefs: {} as never,
} as UserProfile;

const okEntry: FamilyPresenceEntry = {
  user_id: 'u2', display_name: 'Bob', avatar_emoji: '🙂',
  last_heard: null, last_ok: new Date().toISOString(), missed_checkin: false,
};

const missedEntry: FamilyPresenceEntry = {
  user_id: 'u3', display_name: 'Cam', avatar_emoji: '🙂',
  last_heard: null, last_ok: null, missed_checkin: true,
};

const base = {
  profile, connected: true, uiLevel: 'simple' as const, ncsEnabled: true,
  unreadCount: 0, familyEntries: [] as FamilyPresenceEntry[], isKid: false,
  onOpenActivity: vi.fn(), onOpenSettings: vi.fn(), onLogout: vi.fn(),
};

describe('HomeScreen', () => {
  it('simple tier shows Chat card but no Net Control card', () => {
    render(<HomeScreen {...base} />);
    expect(screen.getByRole('button', { name: /chat/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /net control/i })).toBeNull();
  });

  it('operator tier shows Net Control card when NCS enabled', () => {
    render(<HomeScreen {...base} uiLevel="operator" />);
    expect(screen.getByRole('button', { name: /net control/i })).toBeInTheDocument();
  });

  it('clicking Chat opens station activity', () => {
    const onOpenActivity = vi.fn();
    render(<HomeScreen {...base} onOpenActivity={onOpenActivity} />);
    fireEvent.click(screen.getByRole('button', { name: /chat/i }));
    expect(onOpenActivity).toHaveBeenCalledWith('station');
  });

  it('arrow keys move focus between cards (roving tabindex)', () => {
    render(<HomeScreen {...base} uiLevel="operator" />);
    const grid = screen.getByRole('list', { name: /activities/i });
    const cards = within(grid).getAllByRole('button');
    cards[0].focus();
    fireEvent.keyDown(cards[0], { key: 'ArrowRight' });
    expect(cards[1]).toHaveFocus();
    expect(cards[0]).toHaveAttribute('tabindex', '-1');
    expect(cards[1]).toHaveAttribute('tabindex', '0');
  });

  it('keeps a tabbable card after cards shrink out from under a stale focus index', () => {
    const { rerender } = render(<HomeScreen {...base} uiLevel="operator" />);
    const grid = screen.getByRole('list', { name: /activities/i });
    let cards = within(grid).getAllByRole('button');
    cards[0].focus();
    fireEvent.keyDown(cards[0], { key: 'ArrowRight' }); // focusIdx -> 1 (Family card)
    fireEvent.keyDown(cards[1], { key: 'ArrowRight' }); // focusIdx -> 2 (Net Control card)
    expect(cards[2]).toHaveAttribute('tabindex', '0');

    // uiLevel drops to simple — Net Control card disappears, Chat + Family remain.
    rerender(<HomeScreen {...base} uiLevel="simple" />);
    cards = within(grid).getAllByRole('button');
    expect(cards).toHaveLength(2);
    expect(cards[1]).toHaveAttribute('tabindex', '0');
  });

  it('shows unread badge on Chat card', () => {
    render(<HomeScreen {...base} unreadCount={3} />);
    expect(screen.getByText(/3 new/i)).toBeInTheDocument();
  });

  it('folds the unread count into the Chat card accessible name', () => {
    // aria-label overrides a button's text-content accessible name, so the
    // "3 new" subtitle text alone is invisible to screen readers unless
    // it's also reflected in aria-label.
    render(<HomeScreen {...base} unreadCount={3} />);
    expect(screen.getByRole('button', { name: 'Chat, 3 new' })).toBeInTheDocument();
  });

  it('omits the unread suffix from the accessible name when there are no unread messages', () => {
    render(<HomeScreen {...base} unreadCount={0} />);
    expect(screen.getByRole('button', { name: 'Chat' })).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = render(<HomeScreen {...base} uiLevel="operator" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('shows the Family card in simple tier', () => {
    render(<HomeScreen {...base} />);
    expect(screen.getByRole('button', { name: /family/i })).toBeInTheDocument();
  });

  it('shows the Family card in operator tier', () => {
    render(<HomeScreen {...base} uiLevel="operator" />);
    expect(screen.getByRole('button', { name: /family/i })).toBeInTheDocument();
  });

  it('summarizes an all-clear family roster as "Everyone OK"', () => {
    render(<HomeScreen {...base} familyEntries={[okEntry]} />);
    expect(screen.getByText('Everyone OK')).toBeInTheDocument();
  });

  it('summarizes a missed check-in on the Family card', () => {
    render(<HomeScreen {...base} familyEntries={[okEntry, missedEntry]} />);
    expect(screen.getByText('1 missed check-in')).toBeInTheDocument();
  });

  it('pluralizes multiple missed check-ins on the Family card', () => {
    const missedEntry2: FamilyPresenceEntry = {
      user_id: 'u4', display_name: 'Deb', avatar_emoji: '🙂',
      last_heard: null, last_ok: null, missed_checkin: true,
    };
    render(<HomeScreen {...base} familyEntries={[missedEntry, missedEntry2]} />);
    expect(screen.getByText('2 missed check-ins')).toBeInTheDocument();
  });

  it('folds a missed check-in into the Family card accessible name', () => {
    render(<HomeScreen {...base} familyEntries={[okEntry, missedEntry]} />);
    expect(screen.getByRole('button', { name: 'Family, 1 missed check-in' })).toBeInTheDocument();
  });

  it('does not fold "Everyone OK" into the Family card accessible name', () => {
    render(<HomeScreen {...base} familyEntries={[okEntry]} />);
    expect(screen.getByRole('button', { name: 'Family' })).toBeInTheDocument();
  });

  it('clicking Family opens the family activity', () => {
    const onOpenActivity = vi.fn();
    render(<HomeScreen {...base} onOpenActivity={onOpenActivity} />);
    fireEvent.click(screen.getByRole('button', { name: /family/i }));
    expect(onOpenActivity).toHaveBeenCalledWith('family');
  });

  it('hides the Settings button for kid accounts', () => {
    render(<HomeScreen {...base} isKid />);
    expect(screen.queryByRole('button', { name: 'Settings' })).not.toBeInTheDocument();
  });
});
