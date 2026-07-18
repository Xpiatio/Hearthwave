import { render as rtlRender, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect } from 'vitest';
import { MemberCard } from '../MemberCard';
import type { FamilyPresenceEntry } from '../../../types/ws';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

describe('MemberCard', () => {
  it('shows "Missed check-in" even when last_heard is recent (missed_checkin overrides on-air/ok status)', () => {
    const now = new Date();
    const entry: FamilyPresenceEntry = {
      user_id: 'u1',
      display_name: 'U1',
      avatar_emoji: '🙂',
      last_heard: now.toISOString(), // would otherwise read "on_air"
      last_ok: now.toISOString(), // would otherwise read "OK"
      missed_checkin: true,
    };
    render(<MemberCard entry={entry} now={now} />);
    expect(screen.getByText('Missed check-in')).toBeInTheDocument();
    expect(screen.queryByText('On air')).not.toBeInTheDocument();
    expect(screen.queryByText(/^OK/)).not.toBeInTheDocument();
  });
});
