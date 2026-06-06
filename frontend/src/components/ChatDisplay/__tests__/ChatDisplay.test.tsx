import React from 'react'
import { render as rtlRender, screen, fireEvent, within } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ChatDisplay, ChatEntry } from '../ChatDisplay'
import type { Contact } from '../../../types/ws'

// jsdom doesn't implement scrollIntoView — provide a no-op stub globally.
window.HTMLElement.prototype.scrollIntoView = vi.fn()

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeEntry(overrides: Partial<ChatEntry> = {}): ChatEntry {
  return {
    id: 'msg-1',
    timestamp: '12:34:56',
    kind: 'rx',
    text: 'Hello world',
    ...overrides,
  }
}

const NO_CONTACTS: Contact[] = []

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('ChatDisplay — empty state', () => {
  it('shows placeholder when entries is empty', () => {
    render(
      <ChatDisplay
        entries={[]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText(/No messages yet/i)).toBeInTheDocument()
  })

  it('does not show placeholder when there are entries', () => {
    render(
      <ChatDisplay
        entries={[makeEntry()]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.queryByText(/No messages yet/i)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Message rendering — kinds
// ---------------------------------------------------------------------------

describe('ChatDisplay — message kinds', () => {
  it('renders [RX] label for rx voice messages', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'rx', source: 'voice' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByLabelText('Received from radio')).toBeInTheDocument()
    expect(screen.getByLabelText('Received from radio')).toHaveTextContent('[RX]')
  })

  it('renders [RX] label for rx messages with no source', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'rx' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByLabelText('Received from radio')).toBeInTheDocument()
  })

  it('renders [CW] label for rx cw messages', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'rx', source: 'cw' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByLabelText('Received morse code')).toBeInTheDocument()
    expect(screen.getByLabelText('Received morse code')).toHaveTextContent('[CW]')
  })

  it('renders [TX] label for tx messages', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'tx', text: 'Transmitting' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByLabelText('Sent by you')).toBeInTheDocument()
    expect(screen.getByLabelText('Sent by you')).toHaveTextContent('[TX]')
  })

  it('renders [SYS] label for system messages', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'system', text: 'System notice' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByLabelText('System message')).toBeInTheDocument()
    expect(screen.getByLabelText('System message')).toHaveTextContent('[SYS]')
  })

  it('renders timestamp for each entry', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ timestamp: '09:15:00' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('09:15:00')).toBeInTheDocument()
  })

  it('renders message text', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ text: 'Break break' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('Break break')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Multiple messages
// ---------------------------------------------------------------------------

describe('ChatDisplay — multiple entries', () => {
  it('renders all entries in order', () => {
    const entries: ChatEntry[] = [
      makeEntry({ id: 'a', timestamp: '10:00', text: 'First' }),
      makeEntry({ id: 'b', timestamp: '10:01', text: 'Second' }),
      makeEntry({ id: 'c', timestamp: '10:02', text: 'Third' }),
    ]
    render(
      <ChatDisplay
        entries={entries}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('First')).toBeInTheDocument()
    expect(screen.getByText('Second')).toBeInTheDocument()
    expect(screen.getByText('Third')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Partial messages
// ---------------------------------------------------------------------------

describe('ChatDisplay — partial messages', () => {
  it('shows ellipsis indicator for partial entries', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ partial: true, text: 'Incom' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    // The … span is rendered for partial messages
    expect(screen.getByText(/…/)).toBeInTheDocument()
  })

  it('does not show ellipsis for final (non-partial) entries', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ partial: false, text: 'Complete message' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.queryByText(/…/)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Sender / recipient
// ---------------------------------------------------------------------------

describe('ChatDisplay — sender and recipient', () => {
  it('renders sender bracket without colon when recipient is present', () => {
    render(
      <ChatDisplay
        entries={[
          makeEntry({
            sender: 'WSLZ233',
            recipient: 'KD9XYZ — Dave',
            text: 'Go ahead',
          }),
        ]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('[WSLZ233]')).toBeInTheDocument()
    expect(screen.getByText('→ KD9XYZ — Dave:')).toBeInTheDocument()
  })

  it('renders sender with colon when no recipient', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ sender: 'KD9XYZ', text: 'General call' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('[KD9XYZ]:')).toBeInTheDocument()
  })

  it('renders speaker in brackets when present', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ speaker: 'Dave' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('[Dave]')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Callsign chips — regex fallback
// ---------------------------------------------------------------------------

describe('ChatDisplay — callsign chips (regex fallback)', () => {
  it('renders callsign chips for rx messages when showCallsignChips=true', () => {
    render(
      <ChatDisplay
        entries={[
          makeEntry({
            kind: 'rx',
            text: 'This is WSLZ233 calling',
          }),
        ]}
        contacts={NO_CONTACTS}
        showCallsignChips={true}
      />
    )
    // MUI Chip renders the label in a span
    expect(screen.getByText('WSLZ233')).toBeInTheDocument()
  })

  it('does not render chips for tx messages even when showCallsignChips=true', () => {
    render(
      <ChatDisplay
        entries={[
          makeEntry({
            kind: 'tx',
            text: 'K1ABC test',
          }),
        ]}
        contacts={NO_CONTACTS}
        showCallsignChips={true}
      />
    )
    // Should render text as-is, not as a chip — text still present but no chip role
    expect(screen.getByText('K1ABC test')).toBeInTheDocument()
  })

  it('renders plain text when showCallsignChips=false', () => {
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'rx', text: 'K1ABC calling' })]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByText('K1ABC calling')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Callsign chips — server-provided spans
// ---------------------------------------------------------------------------

describe('ChatDisplay — callsign spans (server-provided)', () => {
  it('uses server spans to render canonical callsign chip', () => {
    const text = 'Whiskey Sierra Lima Zulu 233 this is KD9XYZ'
    // Span covers "Whiskey Sierra Lima Zulu 233", canonical = WSLZ233
    const spans: Array<[number, number, string]> = [[0, 28, 'WSLZ233']]
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'rx', text, callsign_spans: spans })]}
        contacts={NO_CONTACTS}
        showCallsignChips={true}
      />
    )
    // Chip should show canonical form
    expect(screen.getByText('WSLZ233')).toBeInTheDocument()
  })

  it('applies contact info to chip when callsign is in contacts list', () => {
    const contacts: Contact[] = [
      { callsign: 'WSLZ233', name: 'Dave', location: 'Grand Rapids' },
    ]
    const spans: Array<[number, number, string]> = [[0, 7, 'WSLZ233']]
    render(
      <ChatDisplay
        entries={[makeEntry({ kind: 'rx', text: 'WSLZ233 hello', callsign_spans: spans })]}
        contacts={contacts}
        showCallsignChips={true}
      />
    )
    expect(screen.getByText('WSLZ233')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Scroll button
// ---------------------------------------------------------------------------

describe('ChatDisplay — scroll-to-bottom button', () => {
  it('is not visible initially (at bottom)', () => {
    render(
      <ChatDisplay
        entries={[makeEntry()]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.queryByLabelText('Scroll to latest message')).not.toBeInTheDocument()
  })

  it('appears after scrolling away from the bottom', () => {
    render(
      <ChatDisplay
        entries={[makeEntry()]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    const container = screen.getByRole('main')
    // Simulate being scrolled away from bottom
    Object.defineProperty(container, 'scrollHeight', { configurable: true, value: 1000 })
    Object.defineProperty(container, 'scrollTop', { configurable: true, value: 0 })
    Object.defineProperty(container, 'clientHeight', { configurable: true, value: 200 })
    fireEvent.scroll(container)
    expect(screen.getByLabelText('Scroll to latest message')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('ChatDisplay — accessibility', () => {
  it('has aria-label on the message history container', () => {
    render(
      <ChatDisplay
        entries={[]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    expect(screen.getByRole('main', { name: 'Message history' })).toBeInTheDocument()
  })

  it('has aria-live="polite" on the container', () => {
    render(
      <ChatDisplay
        entries={[]}
        contacts={NO_CONTACTS}
        showCallsignChips={false}
      />
    )
    const container = screen.getByRole('main')
    expect(container).toHaveAttribute('aria-live', 'polite')
  })
})
