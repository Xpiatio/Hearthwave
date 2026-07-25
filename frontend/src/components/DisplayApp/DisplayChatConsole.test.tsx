import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ThemeProvider } from '@mui/material/styles';
import { DisplayChatConsole } from './DisplayChatConsole';
import { makeTheme } from '../../theme';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';

let seq = 0;
function entry(over: Partial<ChatEntry>): ChatEntry {
  const base: ChatEntry = { id: `e-${++seq}`, timestamp: '14:22', kind: 'chat', text: '' };
  return { ...base, ...over };
}

function renderConsole(messages: ChatEntry[], eink = false) {
  return render(
    <ThemeProvider theme={makeTheme(false, { eink })}>
      <DisplayChatConsole messages={messages} eink={eink} />
    </ThemeProvider>,
  );
}

describe('DisplayChatConsole', () => {
  it('renders a direction badge per kind, with CW for morse rx', () => {
    renderConsole([
      entry({ id: 'a', kind: 'rx', text: 'voice', source: 'voice' }),
      entry({ id: 'b', kind: 'rx', text: 'dots', source: 'cw' }),
      entry({ id: 'c', kind: 'tx', text: 'reply' }),
      entry({ id: 'd', kind: 'system', text: 'timeout' }),
      entry({ id: 'e', kind: 'chat', text: 'note' }),
    ]);
    expect(screen.getByText('RX')).toBeInTheDocument();
    expect(screen.getByText('CW')).toBeInTheDocument();
    expect(screen.getByText('TX')).toBeInTheDocument();
    expect(screen.getByText('SYS')).toBeInTheDocument();
    expect(screen.getByText('CHAT')).toBeInTheDocument();
  });

  it('writes a context + timestamp sub-caption per kind', () => {
    renderConsole([
      entry({ id: 'a', kind: 'rx', text: 'x', source: 'voice', timestamp: '09:01' }),
      entry({ id: 'b', kind: 'tx', text: 'y', timestamp: '09:02' }),
      entry({ id: 'c', kind: 'system', text: 'z', timestamp: '09:03' }),
    ]);
    expect(screen.getByText('Transcribed · 09:01')).toBeInTheDocument();
    expect(screen.getByText('Voice synthesis · 09:02')).toBeInTheDocument();
    // System carries the timestamp only, no context word.
    expect(screen.getByText('09:03')).toBeInTheDocument();
  });

  it('renders sender → recipient prefix before the message text', () => {
    renderConsole([entry({ id: 'a', kind: 'tx', sender: 'You', recipient: 'WSLZ233 — Dave', text: 'copy' })]);
    expect(screen.getByText('You → WSLZ233 — Dave:')).toBeInTheDocument();
    expect(screen.getByText('copy')).toBeInTheDocument();
  });

  it('keeps every message — the log scrolls rather than truncating', () => {
    const msgs = Array.from({ length: 8 }, (_, i) => entry({ id: `m${i}`, kind: 'chat', text: `msg ${i}` }));
    renderConsole(msgs);
    for (let i = 0; i < 8; i += 1) {
      expect(screen.getByText(`msg ${i}`)).toBeInTheDocument();
    }
  });

  it('renders newest first', () => {
    renderConsole([
      entry({ id: 'a', kind: 'chat', text: 'oldest' }),
      entry({ id: 'b', kind: 'chat', text: 'middle' }),
      entry({ id: 'c', kind: 'chat', text: 'newest' }),
    ]);
    const log = screen.getByRole('log', { name: /radio log messages/i });
    const rendered = ['oldest', 'middle', 'newest']
      .map((t) => screen.getByText(t))
      .map((el) => Array.from(log.querySelectorAll('*')).indexOf(el));
    expect(rendered[2]).toBeLessThan(rendered[1]);
    expect(rendered[1]).toBeLessThan(rendered[0]);
  });

  it('e-ink suppresses partials and shows finalized only', () => {
    renderConsole(
      [
        entry({ id: 'a', kind: 'rx', text: 'final', source: 'voice' }),
        entry({ id: 'b', kind: 'rx', text: 'streaming', source: 'voice', partial: true }),
      ],
      true,
    );
    expect(screen.getByText('final')).toBeInTheDocument();
    expect(screen.queryByText('streaming')).not.toBeInTheDocument();
  });

  it('non-eink keeps partials with a trailing ellipsis', () => {
    renderConsole([entry({ id: 'a', kind: 'rx', text: 'streaming', source: 'voice', partial: true })]);
    expect(screen.getByText('streaming')).toBeInTheDocument();
    expect(screen.getByText('…')).toBeInTheDocument();
  });

  it('renders an empty-state hint when there are no messages', () => {
    renderConsole([]);
    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
  });
});
