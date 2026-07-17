import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { HomeScreen } from '../HomeScreen';
import type { UserProfile } from '../../../types/ws';

const profile = {
  id: 'u1', display_name: 'Ann', avatar_emoji: '🙂', operator_name: 'Ann',
  callsign: 'WABC123', location: 'Home', is_admin: false, prefs: {} as never,
} as UserProfile;

const base = {
  profile, connected: true, uiLevel: 'simple' as const, ncsEnabled: true,
  unreadCount: 0, onOpenActivity: vi.fn(), onOpenSettings: vi.fn(), onLogout: vi.fn(),
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
    fireEvent.keyDown(cards[0], { key: 'ArrowRight' }); // focusIdx -> 1 (Net Control card)
    expect(cards[1]).toHaveAttribute('tabindex', '0');

    // uiLevel drops to simple — Net Control card disappears, only Chat remains.
    rerender(<HomeScreen {...base} uiLevel="simple" />);
    cards = within(grid).getAllByRole('button');
    expect(cards).toHaveLength(1);
    expect(cards[0]).toHaveAttribute('tabindex', '0');
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
});
