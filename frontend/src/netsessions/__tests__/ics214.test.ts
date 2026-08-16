import { describe, it, expect } from 'vitest'
import { sessionToIcs214Csv, type Ics214Header } from '../ics214'
import type { NetSessionDetail } from '../../types/ws'

const HEADER: Ics214Header = {
  incidentName: 'Ottawa County Windstorm',
  preparedByName: 'Maria, KD8ABC',
  preparedByPosition: 'Net Control Station',
  homeAgency: 'Ottawa County ARES',
}

const SESSION: NetSessionDetail = {
  id: '20260801_190000_neighborhood',
  net_type: 'neighborhood',
  started_at: '2026-08-01T19:00:00Z',
  ended_at: '2026-08-01T19:52:00Z',
  duration_seconds: 3120,
  transcript: 'irrelevant',
  roster: [
    {
      callsign: 'KD8ABC', name: 'Maria', location: 'Holland',
      status: 'CheckedIn', traffic: 'Routine',
      checkin_time: '2026-08-01T19:01:00Z', verified: true,
    },
    {
      callsign: 'WRAB123', name: 'Sam "Radio" Jones', location: 'Zeeland, MI',
      status: 'Standby', traffic: null,
      checkin_time: '2026-08-01T19:03:00Z', verified: false,
      via: 'radio', no_answer: true,
    },
  ],
}

const NOW = new Date('2026-08-01T20:00:00Z')

function lines(session = SESSION, header = HEADER): string[] {
  return sessionToIcs214Csv(session, header, NOW).split('\n')
}

/** Index of the row whose first cell is `label`, or -1. */
function rowIndex(rows: string[], label: string): number {
  return rows.findIndex((r) => r.startsWith(label))
}

describe('sessionToIcs214Csv', () => {
  it('writes the numbered header boxes in ICS-214 order', () => {
    const rows = lines()
    expect(rows[0]).toBe('ICS 214,ACTIVITY LOG')
    expect(rows[1]).toBe('1. Incident Name,"Ottawa County Windstorm"')
    expect(rows[2]).toBe(
      '2. Operational Period,Date/Time From,"2026-08-01 19:00",Date/Time To,"2026-08-01 19:52"'
    )
    expect(rows[3]).toBe('3. Name,"Maria, KD8ABC"')
    expect(rows[4]).toBe('4. ICS Position,"Net Control Station"')
    expect(rows[5]).toBe('5. Home Agency (and Unit),"Ottawa County ARES"')
  })

  it('lists every checked-in station under box 6', () => {
    const rows = lines()
    const start = rowIndex(rows, '6. Resources Assigned')
    expect(rows[start + 1]).toBe('Name,ICS Position,Home Agency (and Unit)')
    expect(rows[start + 2]).toBe('"KD8ABC — Maria","Net Participant",""')
    expect(rows[start + 3]).toBe('"WRAB123 — Sam ""Radio"" Jones","Net Participant",""')
  })

  it('brackets the activity log with net opened and net closed entries', () => {
    const rows = lines()
    const start = rowIndex(rows, '7. Activity Log')
    expect(rows[start + 1]).toBe('Date/Time,Notable Activities')
    expect(rows[start + 2]).toBe('"2026-08-01 19:00","Net opened (Neighborhood)"')
    expect(rows[start + 5]).toBe('"2026-08-01 19:52","Net closed — 2 check-ins"')
  })

  it('folds traffic, status, via and no_answer into the activity text', () => {
    const rows = lines()
    const start = rowIndex(rows, '7. Activity Log')
    expect(rows[start + 3]).toBe(
      '"2026-08-01 19:01","Check-in: KD8ABC — Maria — Holland — Routine traffic"'
    )
    expect(rows[start + 4]).toBe(
      '"2026-08-01 19:03","Check-in: WRAB123 — Sam ""Radio"" Jones — Zeeland, MI' +
        ' — status: Standby — via radio (no answer when called)"'
    )
  })

  it('orders activity entries by check-in time regardless of roster order', () => {
    const rows = lines({
      ...SESSION,
      roster: [SESSION.roster[1], SESSION.roster[0]],
    })
    const start = rowIndex(rows, '7. Activity Log')
    expect(rows[start + 3]).toContain('KD8ABC')
    expect(rows[start + 4]).toContain('WRAB123')
  })

  it('signs off with the export time in box 8', () => {
    const rows = lines()
    const start = rowIndex(rows, '8. Prepared by')
    expect(rows[start]).toBe('8. Prepared by,Name,Position/Title,Signature,Date/Time')
    expect(rows[start + 1]).toBe(
      ',"Maria, KD8ABC","Net Control Station","","2026-08-01 20:00"'
    )
  })

  it('keeps the form intact for an empty roster', () => {
    const rows = lines({ ...SESSION, roster: [] })
    const resources = rowIndex(rows, '6. Resources Assigned')
    // Box 6 header row, then straight to the blank line before box 7.
    expect(rows[resources + 1]).toBe('Name,ICS Position,Home Agency (and Unit)')
    expect(rows[resources + 2]).toBe('')
    const activity = rowIndex(rows, '7. Activity Log')
    expect(rows[activity + 3]).toBe('"2026-08-01 19:52","Net closed — 0 check-ins"')
  })

  it('omits the opened and closed entries when the net has no timestamps', () => {
    const rows = lines({ ...SESSION, started_at: '', ended_at: '' })
    expect(rows[2]).toBe('2. Operational Period,Date/Time From,"",Date/Time To,""')
    const start = rowIndex(rows, '7. Activity Log')
    expect(rows[start + 2]).toContain('Check-in: KD8ABC')
    expect(rows.some((r) => r.includes('Net opened'))).toBe(false)
    expect(rows.some((r) => r.includes('Net closed'))).toBe(false)
  })

  it('escapes quotes and commas coming from the header fields', () => {
    const rows = lines(SESSION, {
      ...HEADER,
      incidentName: 'Storm "Bea", day 2',
      homeAgency: '',
    })
    expect(rows[1]).toBe('1. Incident Name,"Storm ""Bea"", day 2"')
    expect(rows[5]).toBe('5. Home Agency (and Unit),""')
  })

  it('falls back to the raw net type when it has no label', () => {
    const rows = lines({ ...SESSION, net_type: 'skywarn' })
    const start = rowIndex(rows, '7. Activity Log')
    expect(rows[start + 2]).toContain('Net opened (skywarn)')
  })
})
