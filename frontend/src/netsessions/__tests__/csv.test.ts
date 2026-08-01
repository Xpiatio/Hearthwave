import { describe, it, expect } from 'vitest'
import { sessionToCsv, allSessionsToCsv } from '../csv'
import type { NetSessionDetail, NetSessionSummary } from '../../types/ws'

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
      callsign: 'WRAB123', name: 'Sam "Radio" Jones', location: 'Zeeland',
      status: 'Standby', traffic: null,
      checkin_time: '2026-08-01T19:03:00Z', verified: false,
    },
  ],
}

describe('sessionToCsv', () => {
  it('writes a header and one row per check-in', () => {
    const lines = sessionToCsv(SESSION).split('\n')
    expect(lines[0]).toBe('callsign,name,location,status,traffic,checkin_time,via')
    expect(lines).toHaveLength(3)
    expect(lines[1]).toContain('"KD8ABC"')
    expect(lines[1]).toContain('"Routine"')
  })

  it('escapes embedded quotes', () => {
    expect(sessionToCsv(SESSION)).toContain('"Sam ""Radio"" Jones"')
  })

  it('renders a null traffic value as empty', () => {
    const row = sessionToCsv(SESSION).split('\n')[2]
    expect(row).toContain('"WRAB123","Sam ""Radio"" Jones","Zeeland","Standby",""')
  })

  it('returns just the header for an empty roster', () => {
    const empty = { ...SESSION, roster: [] }
    expect(sessionToCsv(empty)).toBe('callsign,name,location,status,traffic,checkin_time,via')
  })

  it('includes a via column so radio check-ins are identifiable in a spreadsheet', () => {
    const csv = sessionToCsv({
      id: 'x', net_type: 'neighborhood', started_at: '', ended_at: '',
      duration_seconds: 0, transcript: '',
      roster: [
        { callsign: 'WRAB123', name: 'Maria', location: 'Maple St', status: 'CheckedIn',
          traffic: null, checkin_time: '2026-08-01T19:30:00Z', verified: false, via: 'radio' },
        { callsign: 'WRAA111', name: 'Ann', location: '1st St', status: 'CheckedIn',
          traffic: null, checkin_time: '2026-08-01T19:31:00Z', verified: false },
      ],
    } as NetSessionDetail)
    const [header, maria, ann] = csv.split('\n')
    expect(header).toBe('callsign,name,location,status,traffic,checkin_time,via')
    expect(maria.endsWith('"radio"')).toBe(true)
    expect(ann.endsWith('""')).toBe(true)
  })
})

describe('allSessionsToCsv', () => {
  const SUMMARIES: NetSessionSummary[] = [
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

  it('writes one row per station per net, with net columns', () => {
    const lines = allSessionsToCsv(SUMMARIES).split('\n')
    expect(lines[0]).toBe('net_id,net_type,net_date,callsign,name')
    expect(lines).toHaveLength(4)
    expect(lines[1]).toContain('"20260802_190000_ncs"')
    expect(lines[1]).toContain('"2026-08-02"')
  })

  it('returns just the header when there are no sessions', () => {
    expect(allSessionsToCsv([])).toBe('net_id,net_type,net_date,callsign,name')
  })

  it('leaves the all-sessions export unchanged', () => {
    // Summaries only carry callsign+name per station, so this export has no via
    // column to fill.
    expect(allSessionsToCsv([]).split('\n')[0]).toBe('net_id,net_type,net_date,callsign,name')
  })
})
