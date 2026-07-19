import React from 'react'
import { render as rtlRender, screen, within, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { axe } from 'jest-axe'
import { AACApp } from '../AACApp'
import type { AACAppProps } from '../AACApp'
import { makeDefaultGrid } from '../defaultGrid'
import type { UserProfile } from '../../../types/ws'

const profile: UserProfile = {
  id: 'u1',
  display_name: 'Ben',
  avatar_emoji: '🙂',
  operator_name: 'Ben',
  callsign: 'WRXB123',
  location: 'Test City',
  is_admin: false,
  role: 'adult',
  created_at: '2026-01-01T00:00:00Z',
  prefs: {
    dark_mode: false,
    filter_profanity: true,
    listen_only: false,
    read_aloud: false,
    notifications_enabled: false,
    spectro_colormap: 'viridis',
    spectro_time_window_s: 30,
  },
}

function makeProps(overrides: Partial<AACAppProps> = {}): AACAppProps {
  return {
    profile,
    effectiveCallsign: 'WRXB123',
    connected: true,
    transmitting: false,
    listenOnly: false,
    messages: [],
    grid: makeDefaultGrid(),
    onSend: vi.fn(),
    onTxAbort: vi.fn(),
    onSaveGrid: vi.fn(),
    onExitAac: vi.fn(),
    switchScan: false,
    switchScanIntervalS: 1.5,
    errorSnack: null,
    onCloseErrorSnack: vi.fn(),
    ...overrides,
  }
}

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AACApp', () => {
  it('renders default categories and Core buttons', () => {
    render(<AACApp {...makeProps()} />)
    expect(screen.getByRole('tab', { name: /Core/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Radio/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Yes' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No' })).toBeInTheDocument()
  })

  it('tapping buttons appends to the sentence strip', async () => {
    const user = userEvent.setup()
    render(<AACApp {...makeProps()} />)
    await user.click(screen.getByRole('button', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'Thank you' }))
    const strip = screen.getByRole('status', { name: 'Message being composed' })
    expect(within(strip).getByText('Yes')).toBeInTheDocument()
    expect(within(strip).getByText('Thank you')).toBeInTheDocument()
  })

  it('backspace removes the last chunk and clear empties the strip', async () => {
    const user = userEvent.setup()
    render(<AACApp {...makeProps()} />)
    await user.click(screen.getByRole('button', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'No' }))
    await user.click(screen.getByRole('button', { name: 'Remove last word' }))
    const strip = screen.getByRole('status', { name: 'Message being composed' })
    expect(within(strip).queryByText('No')).not.toBeInTheDocument()
    expect(within(strip).getByText('Yes')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear message' }))
    expect(within(strip).queryByText('Yes')).not.toBeInTheDocument()
  })

  it('SEND resolves tokens, calls onSend and clears the strip', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<AACApp {...makeProps({ onSend })} />)
    await user.click(screen.getByRole('tab', { name: /Radio/ }))
    await user.click(screen.getByRole('button', { name: 'Check in' }))
    await user.click(screen.getByRole('button', { name: 'Send message over radio' }))
    expect(onSend).toHaveBeenCalledWith('This is WRXB123 checking in', '', '', ['This is {callsign} checking in'])
    const strip = screen.getByRole('status', { name: 'Message being composed' })
    expect(within(strip).getByText(/Tap buttons/)).toBeInTheDocument()
  })

  it('SEND passes the raw button chunks alongside the resolved text', () => {
    const onSend = vi.fn()
    render(<AACApp {...makeProps({ onSend })} />)
    fireEvent.click(within(screen.getByRole('group')).getByRole('button', { name: 'Yes' }))
    fireEvent.click(screen.getByRole('button', { name: 'Send message over radio' }))
    expect(onSend).toHaveBeenCalledWith('Yes', '', '', ['Yes'])
  })

  it('shows server errors in a snackbar', () => {
    render(<AACApp {...makeProps({ errorSnack: 'TX not allowed for this account', onCloseErrorSnack: vi.fn() })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('TX not allowed for this account')
  })

  it('SEND is disabled when strip empty, disconnected, or listen-only', async () => {
    const { unmount } = render(<AACApp {...makeProps()} />)
    expect(screen.getByRole('button', { name: 'Send message over radio' })).toBeDisabled()
    unmount()

    const user = userEvent.setup()
    render(<AACApp {...makeProps({ listenOnly: true })} />)
    await user.click(screen.getByRole('button', { name: 'Yes' }))
    const send = screen.getByRole('button', { name: 'Send message over radio' })
    expect(send).toBeDisabled()
    expect(send).toHaveTextContent(/LISTEN-ONLY/)
  })

  it('shows ABORT while transmitting and wires onTxAbort', async () => {
    const user = userEvent.setup()
    const onTxAbort = vi.fn()
    render(<AACApp {...makeProps({ transmitting: true, onTxAbort })} />)
    await user.click(screen.getByRole('button', { name: 'Abort transmission' }))
    expect(onTxAbort).toHaveBeenCalled()
  })

  it('Exit requires confirmation before calling onExitAac', async () => {
    const user = userEvent.setup()
    const onExitAac = vi.fn()
    render(<AACApp {...makeProps({ onExitAac })} />)
    await user.click(screen.getByRole('button', { name: 'Exit AAC mode' }))
    expect(onExitAac).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Yes, exit/ }))
    expect(onExitAac).toHaveBeenCalled()
  })

  it('edit mode: tapping a button opens the editor instead of appending', async () => {
    const user = userEvent.setup()
    render(<AACApp {...makeProps()} />)
    await user.click(screen.getByRole('button', { name: 'Edit buttons' }))
    await user.click(screen.getByRole('button', { name: 'Edit button: Yes' }))
    expect(screen.getByRole('dialog', { name: 'Edit Button' })).toBeInTheDocument()
    // Dialog aria-hides the background, so query the strip as hidden.
    const strip = screen.getByRole('status', { name: 'Message being composed', hidden: true })
    expect(within(strip).queryByText('Yes')).not.toBeInTheDocument()
  })

  it('edit mode: saving an edited button calls onSaveGrid with the change', async () => {
    const user = userEvent.setup()
    const onSaveGrid = vi.fn()
    render(<AACApp {...makeProps({ onSaveGrid })} />)
    await user.click(screen.getByRole('button', { name: 'Edit buttons' }))
    await user.click(screen.getByRole('button', { name: 'Edit button: Yes' }))
    const label = screen.getByRole('textbox', { name: /Label/ })
    await user.clear(label)
    await user.type(label, 'Affirmative')
    await user.click(screen.getByRole('button', { name: 'SAVE' }))
    expect(onSaveGrid).toHaveBeenCalledTimes(1)
    const saved = onSaveGrid.mock.calls[0][0]
    const core = saved.categories.find((c: { name: string }) => c.name === 'Core')
    expect(core.buttons.map((b: { label: string }) => b.label)).toContain('Affirmative')
  })

  it('edit mode: adding a category calls onSaveGrid', async () => {
    const user = userEvent.setup()
    const onSaveGrid = vi.fn()
    render(<AACApp {...makeProps({ onSaveGrid })} />)
    await user.click(screen.getByRole('button', { name: 'Edit buttons' }))
    await user.click(screen.getByRole('button', { name: 'Add category' }))
    await user.type(screen.getByRole('textbox', { name: /Name/ }), 'Weather')
    await user.click(screen.getByRole('button', { name: 'SAVE' }))
    expect(onSaveGrid).toHaveBeenCalledTimes(1)
    const saved = onSaveGrid.mock.calls[0][0]
    expect(saved.categories.map((c: { name: string }) => c.name)).toContain('Weather')
  })

  it('shows recent incoming messages', () => {
    const messages = [
      { id: '1', timestamp: 't', kind: 'rx' as const, sender: 'W1AW', text: 'Hello there' },
    ]
    render(<AACApp {...makeProps({ messages })} />)
    expect(screen.getByText('Hello there')).toBeInTheDocument()
  })

  it('has no axe violations in normal and edit views', async () => {
    const user = userEvent.setup()
    const { container } = render(<AACApp {...makeProps()} />)
    expect(await axe(container)).toHaveNoViolations()
    await user.click(screen.getByRole('button', { name: 'Edit buttons' }))
    expect(await axe(container)).toHaveNoViolations()
  })

  it('arrow keys move focus between word buttons (roving tabindex)', () => {
    render(<AACApp {...makeProps()} />)
    const words = within(screen.getByRole('group')).getAllByRole('button')
    words[0].focus()
    fireEvent.keyDown(words[0], { key: 'ArrowRight' })
    expect(words[1]).toHaveFocus()
    expect(words[0]).toHaveAttribute('tabindex', '-1')
    expect(words[1]).toHaveAttribute('tabindex', '0')
    fireEvent.keyDown(words[1], { key: 'ArrowLeft' })
    expect(words[0]).toHaveFocus()
  })

  it('switch scanning cycles tabs, word buttons, then SEND', () => {
    vi.useFakeTimers()
    render(<AACApp {...makeProps({ switchScan: true, switchScanIntervalS: 1 })} />)
    fireEvent.click(within(screen.getByRole('group')).getAllByRole('button')[0])
    act(() => { vi.advanceTimersByTime(1000) })
    expect(screen.getAllByRole('tab')[0]).toHaveFocus()
    // advance past all tabs and all word buttons of the active category
    const tabs = screen.getAllByRole('tab').length
    const words = within(screen.getByRole('group')).getAllByRole('button').length
    act(() => { vi.advanceTimersByTime(1000 * (tabs + words)) })
    expect(screen.getByRole('button', { name: 'Send message over radio' })).toHaveFocus()
    vi.useRealTimers()
  })

  it('switch scanning pauses in edit mode', () => {
    vi.useFakeTimers()
    render(<AACApp {...makeProps({ switchScan: true, switchScanIntervalS: 1 })} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit buttons' }))
    act(() => { vi.advanceTimersByTime(3000) })
    expect(screen.getAllByRole('tab')[0]).not.toHaveFocus()
    vi.useRealTimers()
  })
})
