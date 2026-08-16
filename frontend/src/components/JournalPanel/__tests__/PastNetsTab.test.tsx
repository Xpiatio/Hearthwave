import { render as rtlRender, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { PastNetsTab } from '../PastNetsTab'
import { downloadText } from '../../../utils/download'
import type { NetSessionSummary, NetSessionDetail, AttendanceStatRow } from '../../../types/ws'

// Spy on the download helper while letting the real CSV builders run, so
// assertions below cover both the button wiring and the CSV builder output.
vi.mock('../../../utils/download', () => ({
  downloadText: vi.fn(),
}))

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

const SESSIONS: NetSessionSummary[] = [
  {
    id: '20260802_190000_ncs', net_type: 'ncs',
    started_at: '2026-08-02T19:00:00Z', ended_at: '2026-08-02T19:30:00Z',
    duration_seconds: 1800, checkin_count: 1,
    stations: [{ callsign: 'KD8ABC', name: 'Maria' }],
  },
  {
    id: '20260801_190000_neighborhood', net_type: 'neighborhood',
    started_at: '2026-08-01T19:00:00Z', ended_at: '2026-08-01T19:52:00Z',
    duration_seconds: 3120, checkin_count: 2,
    stations: [
      { callsign: 'KD8ABC', name: 'Maria' },
      { callsign: 'WRAB123', name: 'Sam' },
    ],
  },
]

const STATS: AttendanceStatRow[] = [
  {
    callsign: 'KD8ABC', name: 'Maria', total_nets: 2,
    attended_of_recent: 2, recent_window: 2, current_streak: 2,
    last_seen: '2026-08-02T19:00:00Z',
  },
]

const DETAIL: NetSessionDetail = {
  id: '20260802_190000_ncs', net_type: 'ncs',
  started_at: '2026-08-02T19:00:00Z', ended_at: '2026-08-02T19:30:00Z',
  duration_seconds: 1800,
  transcript: 'KD8ABC: nothing to report',
  roster: [{
    callsign: 'KD8ABC', name: 'Maria', location: 'Holland',
    status: 'CheckedIn', traffic: 'Routine',
    checkin_time: '2026-08-02T19:01:00Z', verified: true,
  }],
}

const DETAIL_MULTI_ROW: NetSessionDetail = {
  ...DETAIL,
  roster: [
    ...DETAIL.roster,
    {
      callsign: 'WRAB123', name: 'Sam', location: 'Zeeland',
      status: 'CheckedIn', traffic: 'Routine',
      checkin_time: '2026-08-02T19:02:00Z', verified: false,
    },
    {
      callsign: 'KE8XYZ', name: 'Alex', location: 'Holland',
      status: 'Standby', traffic: 'Priority',
      checkin_time: '2026-08-02T19:03:00Z', verified: false,
    },
  ],
}

function props(overrides = {}) {
  return {
    sessions: SESSIONS, stats: STATS, selected: null, isAdmin: false,
    onSelect: vi.fn(), onDelete: vi.fn(),
    ...overrides,
  }
}

describe('PastNetsTab', () => {
  beforeEach(() => {
    vi.mocked(downloadText).mockClear()
    // The ICS-214 dialog remembers its header fields across exports.
    localStorage.clear()
  })

  it('lists every session with its date and check-in count', () => {
    render(<PastNetsTab {...props()} />)
    expect(screen.getByText('2026-08-02')).toBeInTheDocument()
    expect(screen.getByText('2026-08-01')).toBeInTheDocument()
    expect(screen.getByText(/2 check-ins/)).toBeInTheDocument()
  })

  it('shows an empty state when there are no sessions', () => {
    render(<PastNetsTab {...props({ sessions: [], stats: [] })} />)
    expect(screen.getByText(/No nets recorded yet/i)).toBeInTheDocument()
  })

  it('requests a session detail when one is clicked', () => {
    const onSelect = vi.fn()
    render(<PastNetsTab {...props({ onSelect })} />)
    fireEvent.click(screen.getByText('2026-08-02'))
    expect(onSelect).toHaveBeenCalledWith('20260802_190000_ncs')
  })

  // The print sheet is portalled to <body> and repeats every roster value, so
  // queries about the on-screen table scope themselves to the tab's own
  // container rather than the whole document.
  it('renders the selected session roster', () => {
    const { container } = render(<PastNetsTab {...props({ selected: DETAIL })} />)
    const table = within(container)
    expect(table.getByText('KD8ABC')).toBeInTheDocument()
    expect(table.getByText('Holland')).toBeInTheDocument()
    expect(table.getByText('Routine')).toBeInTheDocument()
  })

  it('hides non-matching rows when a callsign is typed into the roster filter', () => {
    const { container } = render(<PastNetsTab {...props({ selected: DETAIL_MULTI_ROW })} />)
    const filter = screen.getByLabelText(/filter roster/i)
    fireEvent.change(filter, { target: { value: 'KE8XYZ' } })

    const table = within(container)
    expect(table.getByText('KE8XYZ')).toBeInTheDocument()
    expect(table.queryByText('KD8ABC')).not.toBeInTheDocument()
    expect(table.queryByText('WRAB123')).not.toBeInTheDocument()
  })

  it('shows attendance stats', () => {
    render(<PastNetsTab {...props()} />)
    expect(screen.getByText(/Maria/)).toBeInTheDocument()
    expect(screen.getByText(/2 of last 2/)).toBeInTheDocument()
  })

  it('hides the delete control from non-admins', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    expect(screen.queryByRole('button', { name: /delete net record/i })).not.toBeInTheDocument()
  })

  it('deletes after a confirming second click for admins', () => {
    const onDelete = vi.fn()
    render(<PastNetsTab {...props({ selected: DETAIL, isAdmin: true, onDelete })} />)
    const button = screen.getByRole('button', { name: /delete net record/i })
    fireEvent.click(button)
    expect(onDelete).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /confirm delete/i }))
    expect(onDelete).toHaveBeenCalledWith('20260802_190000_ncs')
  })

  it('exports all sessions as CSV when EXPORT ALL (CSV) is clicked', () => {
    render(<PastNetsTab {...props()} />)
    fireEvent.click(screen.getByText('EXPORT ALL (CSV)'))

    expect(downloadText).toHaveBeenCalledTimes(1)
    const [content, filename, mime] = vi.mocked(downloadText).mock.calls[0]
    expect(filename).toBe('net-history.csv')
    expect(mime).toBe('text/csv')

    const lines = content.split('\n')
    expect(lines[0]).toBe('net_id,net_type,net_date,callsign,name')
    expect(lines).toHaveLength(1 + SESSIONS.reduce((n, s) => n + s.stations.length, 0))
    expect(lines[1]).toBe('"20260802_190000_ncs","ncs","2026-08-02","KD8ABC","Maria"')
  })

  it('downloads the selected session as CSV when DOWNLOAD CSV is clicked', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    fireEvent.click(screen.getByText('DOWNLOAD CSV'))

    expect(downloadText).toHaveBeenCalledTimes(1)
    const [content, filename, mime] = vi.mocked(downloadText).mock.calls[0]
    expect(filename).toBe(`${DETAIL.id}.csv`)
    expect(mime).toBe('text/csv')

    const lines = content.split('\n')
    expect(lines[0]).toBe('callsign,name,location,status,traffic,checkin_time,via,no_answer')
    expect(lines).toHaveLength(1 + DETAIL.roster.length)
    expect(lines[1]).toBe(
      '"KD8ABC","Maria","Holland","CheckedIn","Routine","2026-08-02T19:01:00Z","",""'
    )
  })

  /** Open the ICS-214 dialog and fill in the two required boxes. */
  function openIcs214(incidentName = 'Ottawa County Windstorm') {
    fireEvent.click(screen.getByText('ICS-214 (CSV)'))
    fireEvent.change(screen.getByLabelText(/incident name/i), {
      target: { value: incidentName },
    })
    fireEvent.change(screen.getByLabelText(/prepared by/i), {
      target: { value: 'Maria, KD8ABC' },
    })
  }

  it('exports an ICS-214 for the selected session once the dialog is filled in', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    openIcs214()
    fireEvent.click(screen.getByRole('button', { name: /^export$/i }))

    expect(downloadText).toHaveBeenCalledTimes(1)
    const [content, filename, mime] = vi.mocked(downloadText).mock.calls[0]
    expect(filename).toBe(`ICS-214-${DETAIL.id}.csv`)
    expect(mime).toBe('text/csv')

    const lines = content.split('\n')
    // BOM first, so Excel reads the em dashes as UTF-8 instead of the codepage.
    expect(lines[0]).toBe('\ufeffICS 214,ACTIVITY LOG')
    expect(lines[1]).toBe('1. Incident Name,"Ottawa County Windstorm"')
    expect(content).toContain('"KD8ABC — Maria","Net Participant",""')
    expect(content).toContain('"Net opened (Net Control)"')
  })

  it('will not export an ICS-214 until the incident name and preparer are given', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    fireEvent.click(screen.getByText('ICS-214 (CSV)'))
    const exportButton = screen.getByRole('button', { name: /^export$/i })
    expect(exportButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/incident name/i), {
      target: { value: 'Ottawa County Windstorm' },
    })
    expect(exportButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/prepared by/i), {
      target: { value: 'Maria, KD8ABC' },
    })
    expect(exportButton).toBeEnabled()
  })

  it('remembers the ICS-214 header fields for the next export', () => {
    const { unmount } = render(<PastNetsTab {...props({ selected: DETAIL })} />)
    openIcs214()
    fireEvent.change(screen.getByLabelText(/home agency/i), {
      target: { value: 'Ottawa County ARES' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^export$/i }))
    unmount()

    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    fireEvent.click(screen.getByText('ICS-214 (CSV)'))
    expect(screen.getByLabelText(/home agency/i)).toHaveValue('Ottawa County ARES')
    expect(screen.getByLabelText(/incident name/i)).toHaveValue('Ottawa County Windstorm')
  })

  it('closes the ICS-214 dialog once the export is handed off', async () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    openIcs214()
    fireEvent.click(screen.getByRole('button', { name: /^export$/i }))
    // The dialog leaves on a transition, so it outlives the click by a frame.
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /^export$/i })).not.toBeInTheDocument()
    )
  })

  it('opens the ICS-214 dialog with defaults when the saved header is corrupt', () => {
    localStorage.setItem('radio_tty_ics214_header', '{{{ not json')
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    fireEvent.click(screen.getByText('ICS-214 (CSV)'))

    expect(screen.getByLabelText(/incident name/i)).toHaveValue('')
    expect(screen.getByLabelText(/ics position/i)).toHaveValue('Net Control Station')
  })

  it('offers no ICS-214 export until a session is selected', () => {
    render(<PastNetsTab {...props()} />)
    expect(screen.queryByText('ICS-214 (CSV)')).not.toBeInTheDocument()
  })

  it('prints the roster sheet when PRINT ROSTER is clicked', () => {
    const print = vi.fn()
    vi.stubGlobal('print', print)
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    fireEvent.click(screen.getByText('PRINT ROSTER'))
    expect(print).toHaveBeenCalledTimes(1)
    vi.unstubAllGlobals()
  })

  it('keeps a print sheet for the selected net in the document', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    // Portalled to <body>, so it is outside the container the tab renders into.
    const sheet = document.querySelector('.net-roster-sheet')
    expect(sheet).not.toBeNull()
    expect(sheet).toHaveTextContent('KD8ABC')
  })

  it('offers no print sheet until a session is selected', () => {
    render(<PastNetsTab {...props()} />)
    expect(screen.queryByText('PRINT ROSTER')).not.toBeInTheDocument()
    expect(document.querySelector('.net-roster-sheet')).toBeNull()
  })

  it("shows how each station reached the roster", () => {
    const detailWithVia: NetSessionDetail = {
      ...DETAIL,
      roster: [
        DETAIL.roster[0],
        {
          callsign: 'WRAB123', name: 'Sam', location: 'Zeeland',
          status: 'CheckedIn', traffic: null,
          checkin_time: '2026-08-02T19:02:00Z', verified: false, via: 'radio',
        },
      ],
    }
    render(<PastNetsTab {...props({ selected: detailWithVia })} />)
    expect(screen.getByText('Via')).toBeInTheDocument()
    expect(screen.getByText('radio')).toBeInTheDocument()
  })

  it('shows a no-answer column, flagging stations the round-table called with no reply', () => {
    const detailWithNoAnswer: NetSessionDetail = {
      ...DETAIL,
      roster: [
        DETAIL.roster[0],
        {
          callsign: 'WRAB123', name: 'Sam', location: 'Zeeland',
          status: 'CheckedIn', traffic: null,
          checkin_time: '2026-08-02T19:02:00Z', verified: false, no_answer: true,
        },
      ],
    }
    render(<PastNetsTab {...props({ selected: detailWithNoAnswer })} />)
    expect(screen.getByText('No answer')).toBeInTheDocument()
    expect(screen.getByText('yes')).toBeInTheDocument()
  })

  it('filters on "yes", the no-answer flag the user can actually see', () => {
    // DETAIL.roster[0] (KD8ABC) and the Alex row below have no `no_answer` at
    // all, so they render as blank — the filter must not match them, only the
    // row whose column shows the literal text "yes". A third row is needed
    // to clear the roster-count threshold that makes the filter box appear.
    const detailWithNoAnswer: NetSessionDetail = {
      ...DETAIL,
      roster: [
        DETAIL.roster[0],
        {
          callsign: 'WRAB123', name: 'Sam', location: 'Zeeland',
          status: 'CheckedIn', traffic: null,
          checkin_time: '2026-08-02T19:02:00Z', verified: false, no_answer: true,
        },
        {
          callsign: 'KE8XYZ', name: 'Alex', location: 'Holland',
          status: 'Standby', traffic: null,
          checkin_time: '2026-08-02T19:03:00Z', verified: false,
        },
      ],
    }
    const { container } = render(<PastNetsTab {...props({ selected: detailWithNoAnswer })} />)
    const filter = screen.getByLabelText(/filter roster/i)
    fireEvent.change(filter, { target: { value: 'yes' } })

    const table = within(container)
    expect(table.getByText('WRAB123')).toBeInTheDocument()
    expect(table.queryByText('KD8ABC')).not.toBeInTheDocument()
    expect(table.queryByText('KE8XYZ')).not.toBeInTheDocument()
  })
})
