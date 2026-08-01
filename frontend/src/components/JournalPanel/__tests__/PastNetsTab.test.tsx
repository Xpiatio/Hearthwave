import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
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

  it('renders the selected session roster', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    expect(screen.getByText('KD8ABC')).toBeInTheDocument()
    expect(screen.getByText('Holland')).toBeInTheDocument()
    expect(screen.getByText('Routine')).toBeInTheDocument()
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
    expect(lines[0]).toBe('callsign,name,location,status,traffic,checkin_time')
    expect(lines).toHaveLength(1 + DETAIL.roster.length)
    expect(lines[1]).toBe(
      '"KD8ABC","Maria","Holland","CheckedIn","Routine","2026-08-02T19:01:00Z"'
    )
  })
})
