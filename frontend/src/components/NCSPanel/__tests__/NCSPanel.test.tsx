import { render as rtlRender, screen, fireEvent, act, waitFor, within } from '@testing-library/react'
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
      expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: 'ncs_checkin', callsign: 'W1BBB', traffic: 'Routine' }))
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
      expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: 'ncs_checkin', callsign: 'W1CCC', traffic: 'Routine' }))
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
      expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: 'ncs_status_update', callsign: 'W1AAA', status: 'Standby' }))
    })

    it('sends ncs_remove when delete button clicked', () => {
      const send = renderWithRoster()
      fireEvent.click(screen.getByRole('button', { name: /remove w1aaa/i }))
      expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: 'ncs_remove', callsign: 'W1AAA' }))
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

  describe('SKYWARN spot report', () => {
    // MUI Dialog/Select FocusTrap installs a repeating interval, so runAllTimers
    // would loop forever. The portal content mounts synchronously on open, so we
    // can query without flushing the transition timers.
    function openComposer() {
      fireEvent.click(screen.getByRole('button', { name: /spot report/i }))
    }

    function selectHazard(label: string) {
      fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Hazard' }))
      fireEvent.click(screen.getByRole('option', { name: label }))
    }

    it('spot report button is available even when net is inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByRole('button', { name: /spot report/i })).toBeEnabled()
    })

    it('opens the composer dialog', () => {
      render(<NCSPanel {...makeProps()} />)
      openComposer()
      expect(screen.getByText('SKYWARN Spot Report')).toBeInTheDocument()
    })

    it('disables transmit until a location is entered', () => {
      render(<NCSPanel {...makeProps()} />)
      openComposer()
      const dialog = screen.getByRole('dialog')
      const transmit = within(dialog).getByRole('button', { name: /transmit report/i })
      expect(transmit).toBeDisabled()
      fireEvent.change(within(dialog).getByLabelText(/location/i), { target: { value: 'Hastings, MI' } })
      expect(transmit).toBeEnabled()
    })

    it('sends ncs_spot_report with the structured payload on submit', () => {
      const send = vi.fn()
      render(<NCSPanel {...makeProps({ send })} />)
      openComposer()
      const dialog = screen.getByRole('dialog')
      fireEvent.change(within(dialog).getByLabelText(/location/i), { target: { value: 'Hastings, MI' } })
      fireEvent.click(within(dialog).getByRole('button', { name: /transmit report/i }))
      expect(send).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'ncs_spot_report',
          hazard: 'tornado',
          location: 'Hastings, MI',
          observed_at: expect.any(String),
        }),
      )
    })

    it('keeps transmit disabled for sub-threshold hail and enables at 1 inch', () => {
      render(<NCSPanel {...makeProps()} />)
      openComposer()
      selectHazard('Hail')
      const dialog = screen.getByRole('dialog')
      fireEvent.change(within(dialog).getByLabelText(/location/i), { target: { value: 'Grand Rapids' } })
      const transmit = within(dialog).getByRole('button', { name: /transmit report/i })
      fireEvent.change(within(dialog).getByLabelText(/largest hailstone/i), { target: { value: '0.5' } })
      expect(transmit).toBeDisabled()
      fireEvent.change(within(dialog).getByLabelText(/largest hailstone/i), { target: { value: '1.75' } })
      expect(transmit).toBeEnabled()
    })

    it('shows a confirmation notice on ncs_spot_report_sent', () => {
      const msg: WsMessage = { type: 'ncs_spot_report_sent', text: 'SKYWARN SPOT REPORT. ...', ts: 't' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('Spot report transmitted.')).toBeInTheDocument()
    })

    it('surfaces the server error in the open composer on ncs_spot_report_error', () => {
      const { rerender } = render(<NCSPanel {...makeProps()} />)
      openComposer()
      const errMsg: WsMessage = {
        type: 'ncs_spot_report_error',
        detail: 'Hail under 1.00 inch is below SKYWARN reporting criteria.',
      }
      rerender(
        <ThemeProvider theme={makeTheme(false)}>
          <NCSPanel {...makeProps({ lastMessage: errMsg })} />
        </ThemeProvider>,
      )
      expect(screen.getByText(/below SKYWARN reporting criteria/i)).toBeInTheDocument()
    })
  })

  describe('net scripts and round-table', () => {
    const ACTIVE: WsMessage = { type: 'ncs_state', active: true, roster: [], zone: '' }

    it('script and round-table buttons are disabled when inactive', () => {
      render(<NCSPanel {...makeProps()} />)
      expect(screen.getByRole('button', { name: /read preamble/i })).toBeDisabled()
      expect(screen.getByRole('button', { name: /read closing/i })).toBeDisabled()
      expect(screen.getByRole('button', { name: /call next station/i })).toBeDisabled()
      expect(screen.getByRole('button', { name: /new round/i })).toBeDisabled()
    })

    it('sends ncs_read_preamble / ncs_read_closing when active', () => {
      const send = vi.fn()
      render(<NCSPanel {...makeProps({ send, lastMessage: ACTIVE })} />)
      fireEvent.click(screen.getByRole('button', { name: /read preamble/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_read_preamble' })
      fireEvent.click(screen.getByRole('button', { name: /read closing/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_read_closing' })
    })

    it('sends ncs_call_next and ncs_call_reset when active', () => {
      const send = vi.fn()
      render(<NCSPanel {...makeProps({ send, lastMessage: ACTIVE })} />)
      fireEvent.click(screen.getByRole('button', { name: /call next station/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_call_next' })
      fireEvent.click(screen.getByRole('button', { name: /new round/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_call_reset' })
    })

    it('per-row call button sends ncs_call_station', () => {
      const send = vi.fn()
      const msg: WsMessage = {
        type: 'ncs_state', active: true, zone: '',
        roster: [{ callsign: 'W1AAA', status: 'CheckedIn', traffic: 'Routine', name: 'Alice', location: 'GR', checkin_time: 1700000000 }],
      }
      render(<NCSPanel {...makeProps({ send, lastMessage: msg })} />)
      fireEvent.click(screen.getByRole('button', { name: /call W1AAA/i }))
      expect(send).toHaveBeenCalledWith({ type: 'ncs_call_station', callsign: 'W1AAA', name: 'Alice' })
    })

    it('shows a notice on ncs_script_sent', () => {
      const msg: WsMessage = { type: 'ncs_script_sent', which: 'preamble', text: '...' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('Preamble transmitted.')).toBeInTheDocument()
    })

    it('shows the error on ncs_script_error', () => {
      const msg: WsMessage = { type: 'ncs_script_error', detail: 'No preamble script configured.' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText('No preamble script configured.')).toBeInTheDocument()
    })

    it('shows a notice on ncs_round_complete', () => {
      const msg: WsMessage = { type: 'ncs_round_complete' }
      render(<NCSPanel {...makeProps({ lastMessage: msg })} />)
      expect(screen.getByText(/round complete/i)).toBeInTheDocument()
    })
  })
})
