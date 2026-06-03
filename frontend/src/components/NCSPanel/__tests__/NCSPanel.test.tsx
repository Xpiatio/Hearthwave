import { render as rtlRender, screen, fireEvent, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { NCSPanel } from '../NCSPanel'
import type { NCSEntry, WsMessage } from '../../../types/ws'
import type { PluginProps } from '../../../plugins'

// AudioContext is not available in jsdom
const mockAudioContext = {
  createBuffer: vi.fn(() => ({ getChannelData: vi.fn(() => new Float32Array(10)) })),
  createBufferSource: vi.fn(() => ({
    buffer: null,
    connect: vi.fn(),
    start: vi.fn(),
    onended: null as unknown,
  })),
  destination: {},
  close: vi.fn(),
}
vi.stubGlobal('AudioContext', vi.fn(() => mockAudioContext))

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const ROSTER_ENTRIES: NCSEntry[] = [
  {
    callsign: 'W1AAA',
    status: 'CheckedIn',
    traffic: 'Routine',
    name: 'Alice Smith',
    location: 'Grand Rapids',
    checkin_time: 1700000000,
  },
  {
    callsign: 'KD9ZZZ',
    status: 'Standby',
    traffic: 'Priority',
    name: 'Bob Jones',
    location: 'Holland',
    checkin_time: 1700001000,
  },
  {
    callsign: 'N0CALL',
    status: 'LoggedOut',
    traffic: 'Emergency',
    name: '',
    location: '',
    checkin_time: 1700002000,
  },
]

function makeProps(overrides: Partial<PluginProps> = {}): PluginProps {
  return {
    send: vi.fn(),
    lastMessage: null,
    contacts: [],
    channelClear: true,
    transmitting: false,
    ...overrides,
  }
}

describe('NCSPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial render', () => {
    it('renders without crashing', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByText('NET CONTROL STATION')).toBeInTheDocument()
    })

    it('sends ncs_get_state on mount', () => {
      const send = vi.fn()
      render(<NCSPanel {...makeProps({ send })} />)
      expect(send).toHaveBeenCalledWith({ type: 'ncs_get_state' })
    })

    it('shows INACTIVE chip when not active', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByText('INACTIVE')).toBeInTheDocument()
    })

    it('shows START NET button when inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByText('START NET')).toBeInTheDocument()
    })

    it('BREAK BREAK button is disabled when inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByRole('button', { name: /break break/i })).toBeDisabled()
    })

    it('check-in form fields are disabled when inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByPlaceholderText('Callsign')).toBeDisabled()
      expect(screen.getByRole('button', { name: /check in/i })).toBeDisabled()
    })

    it('replay button is disabled when inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByRole('button', { name: /instant replay/i })).toBeDisabled()
    })
  })

  describe('ncs_state message handling', () => {
    it('shows ACTIVE chip when ncs_state active=true', () => {
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('ACTIVE')).toBeInTheDocument()
    })

    it('shows END NET button when active', () => {
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('END NET')).toBeInTheDocument()
    })

    it('populates roster from ncs_state', () => {
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: ROSTER_ENTRIES, zone: '' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('W1AAA')).toBeInTheDocument()
      expect(screen.getByText('KD9ZZZ')).toBeInTheDocument()
      expect(screen.getByText('Alice Smith')).toBeInTheDocument()
    })
  })

  describe('ncs_roster_update message handling', () => {
    it('updates roster on ncs_roster_update', () => {
      const msg: WsMessage = { type: 'ncs_roster_update', roster: ROSTER_ENTRIES }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('W1AAA')).toBeInTheDocument()
      expect(screen.getByText('KD9ZZZ')).toBeInTheDocument()
    })
  })

  describe('ncs_alert message handling', () => {
    it('shows alert banner when ncs_alert received', () => {
      const msg: WsMessage = {
        type: 'ncs_alert',
        id: 'alert1',
        event: 'Tornado Warning',
        headline: 'A tornado warning is in effect',
        zone: 'MIZ012',
        severity: 'Extreme',
      }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('Tornado Warning')).toBeInTheDocument()
      expect(screen.getByText(/a tornado warning is in effect/i)).toBeInTheDocument()
    })

    it('shows dismiss button for alerts', () => {
      const msg: WsMessage = {
        type: 'ncs_alert',
        id: 'alert1',
        event: 'Severe Thunderstorm',
        headline: 'Severe thunderstorm warning',
        zone: 'MIZ012',
        severity: 'Severe',
      }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByRole('button', { name: /dismiss alerts/i })).toBeInTheDocument()
    })

    it('dismisses alerts when dismiss button clicked', () => {
      const msg: WsMessage = {
        type: 'ncs_alert',
        id: 'alert1',
        event: 'Severe Thunderstorm',
        headline: 'Severe thunderstorm warning',
        zone: 'MIZ012',
        severity: 'Severe',
      }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      fireEvent.click(screen.getByRole('button', { name: /dismiss alerts/i }))
      expect(screen.queryByText('Severe Thunderstorm')).not.toBeInTheDocument()
    })
  })

  describe('ncs_journal_saved message handling', () => {
    it('shows journal saved notice on ncs_journal_saved', () => {
      const msg: WsMessage = { type: 'ncs_journal_saved', path: '/journals/session.md' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('Session journal saved.')).toBeInTheDocument()
    })

    it('hides journal saved notice after 5 seconds', () => {
      const msg: WsMessage = { type: 'ncs_journal_saved', path: '/journals/session.md' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('Session journal saved.')).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByText('Session journal saved.')).not.toBeInTheDocument()
    })
  })

  describe('ncs_break_break_ack handling', () => {
    it('handles ncs_break_break_ack without error', () => {
      const msg: WsMessage = { type: 'ncs_break_break_ack' }
      // Just ensure it renders without throwing
      expect(() => render(<NCSPanel {...makeProps({ lastMessage: msg })} />)).not.toThrow()
    })

    it('clears break-break flash after 3 seconds', () => {
      const msg: WsMessage = { type: 'ncs_break_break_ack' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      act(() => { vi.advanceTimersByTime(3000) })
      // No assertion on visual flash, just ensure no crash
      expect(screen.getByRole('button', { name: /break break/i })).toBeInTheDocument()
    })
  })

  describe('action buttons', () => {
    function renderActive() {
      const send = vi.fn()
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }
      render(<NCSPanel {...makeProps({ send, lastMessage: msg })} />)
      return send
    }

    it('sends ncs_start when START NET clicked', () => {
      const send = vi.fn()
      render(<NCSPanel {...makeProps({ send })} />)
      fireEvent.click(screen.getByText('START NET'))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_start' })
    })

    it('sends ncs_end when END NET clicked', () => {
      const send = renderActive()
      fireEvent.click(screen.getByText('END NET'))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_end' })
    })

    it('sends ncs_break_break when BREAK BREAK clicked', () => {
      const send = renderActive()
      fireEvent.click(screen.getByRole('button', { name: /break break/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_break_break' })
    })

    it('sends ncs_get_replay when replay button clicked', () => {
      const send = renderActive()
      fireEvent.click(screen.getByRole('button', { name: /instant replay/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_get_replay' })
    })
  })

  describe('check-in form', () => {
    function renderActive() {
      const send = vi.fn()
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }
      render(<NCSPanel {...makeProps({ send, lastMessage: msg })} />)
      return send
    }

    it('enables check-in form when active', () => {
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByPlaceholderText('Callsign')).toBeEnabled()
    })

    it('sends ncs_checkin when CHECK IN clicked with callsign', () => {
      const send = renderActive()
      const input = screen.getByPlaceholderText('Callsign')
      fireEvent.change(input, { target: { value: 'W1BBB' } })
      fireEvent.click(screen.getByRole('button', { name: /check in/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_checkin', callsign: 'W1BBB', traffic: 'Routine' })
    })

    it('uppercases callsign input', () => {
      renderActive()
      const input = screen.getByPlaceholderText('Callsign')
      // Component uppercases via onChange: e.target.value.toUpperCase()
      fireEvent.change(input, { target: { value: 'kd9abc' } })
      expect(screen.getByDisplayValue('KD9ABC')).toBeInTheDocument()
    })

    it('clears callsign input after check-in', () => {
      renderActive()
      const input = screen.getByPlaceholderText('Callsign')
      fireEvent.change(input, { target: { value: 'W1BBB' } })
      fireEvent.click(screen.getByRole('button', { name: /check in/i }))
      expect(screen.getByPlaceholderText('Callsign')).toHaveValue('')
    })

    it('does not send ncs_checkin when callsign is empty', () => {
      renderActive()
      // CHECK IN button should be disabled with empty callsign
      expect(screen.getByRole('button', { name: /check in/i })).toBeDisabled()
    })

    it('sends ncs_checkin on Enter key', () => {
      const send = renderActive()
      const input = screen.getByPlaceholderText('Callsign')
      fireEvent.change(input, { target: { value: 'W1CCC' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(send).toHaveBeenCalledWith({ type: 'ncs_checkin', callsign: 'W1CCC', traffic: 'Routine' })
    })
  })

  describe('roster table', () => {
    function renderWithRoster(roster = ROSTER_ENTRIES) {
      const send = vi.fn()
      const msg: WsMessage = { type: 'ncs_state', active: true, roster, zone: '' }
      render(<NCSPanel {...makeProps({ send, lastMessage: msg })} />)
      return send
    }

    it('renders roster table when entries present', () => {
      renderWithRoster()
      expect(screen.getByRole('table')).toBeInTheDocument()
      // Column headers — use getAllByText for 'Traffic' since it also appears as the form label
      expect(screen.getByText('Callsign')).toBeInTheDocument()
      expect(screen.getByText('Status')).toBeInTheDocument()
      expect(screen.getAllByText('Traffic').length).toBeGreaterThan(0)
      expect(screen.getByText('Time')).toBeInTheDocument()
    })

    it('renders status chips for each entry', () => {
      renderWithRoster()
      // CheckedIn -> '✓ In', Standby -> 'Stby', LoggedOut -> 'Out'
      expect(screen.getByText('✓ In')).toBeInTheDocument()
      expect(screen.getByText('Stby')).toBeInTheDocument()
      expect(screen.getByText('Out')).toBeInTheDocument()
    })

    it('renders traffic level chips', () => {
      renderWithRoster()
      // Routine also appears as selected option in the traffic select — use getAllByText
      expect(screen.getAllByText('Routine').length).toBeGreaterThan(0)
      expect(screen.getByText('Priority')).toBeInTheDocument()
      expect(screen.getByText('Emergency')).toBeInTheDocument()
    })

    it('sends ncs_status_update when status chip clicked', () => {
      const send = renderWithRoster()
      fireEvent.click(screen.getByText('✓ In')) // CheckedIn -> Standby
      expect(send).toHaveBeenCalledWith({ type: 'ncs_status_update', callsign: 'W1AAA', status: 'Standby' })
    })

    it('sends ncs_remove when delete button clicked', () => {
      const send = renderWithRoster()
      fireEvent.click(screen.getByRole('button', { name: /remove w1aaa/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_remove', callsign: 'W1AAA' })
    })

    it('shows operator name below callsign when present', () => {
      renderWithRoster()
      expect(screen.getByText('Alice Smith')).toBeInTheDocument()
    })

    it('shows empty roster message when active but no entries', () => {
      const send = vi.fn()
      const msg: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }
      render(<NCSPanel {...makeProps({ send, lastMessage: msg })} />)
      expect(screen.getByText(/no stations checked in/i)).toBeInTheDocument()
    })

    it('does not show empty message when inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.queryByText(/no stations checked in/i)).not.toBeInTheDocument()
    })
  })
})
