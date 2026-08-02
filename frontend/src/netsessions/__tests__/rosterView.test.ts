import { describe, it, expect } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { filterRoster, sortRoster, useRosterSort } from '../rosterView'

const ROWS = [
  { callsign: 'WRAB123', name: 'Sam', location: 'Zeeland' },
  { callsign: 'KD8ABC', name: 'Maria', location: 'Holland' },
  { callsign: 'KE8XYZ', name: 'Alex', location: 'Holland' },
]

const KEYS: (keyof (typeof ROWS)[number])[] = ['callsign', 'name', 'location']

describe('filterRoster', () => {
  it('returns every row for a blank query', () => {
    expect(filterRoster(ROWS, '', KEYS)).toHaveLength(3)
  })

  it('matches a callsign case-insensitively', () => {
    expect(filterRoster(ROWS, 'kd8', KEYS)).toEqual([ROWS[1]])
  })

  it('matches any field in the given key list', () => {
    expect(filterRoster(ROWS, 'holland', KEYS)).toHaveLength(2)
  })

  it('returns nothing when no row matches', () => {
    expect(filterRoster(ROWS, 'nobody', KEYS)).toEqual([])
  })

  it('does not match a field left out of the key list', () => {
    // "Zeeland" only appears in `location`; restricting keys to callsign/name
    // must not match it — this is the hidden-field bug the explicit `keys`
    // param exists to prevent.
    expect(filterRoster(ROWS, 'zeeland', ['callsign', 'name'])).toEqual([])
  })

  it('matches "yes", the rendered text of a true boolean field', () => {
    // A boolean like no_answer renders as "yes"/"" (see PastNetsTab), not as
    // its raw true/false — the filter has to match what's on screen, not the
    // type of the underlying value.
    const rows = [
      { callsign: 'WRAB123', name: 'Sam', no_answer: true },
      { callsign: 'KD8ABC', name: 'Maria', no_answer: false },
    ]
    expect(filterRoster(rows, 'yes', ['callsign', 'name', 'no_answer'])).toEqual([rows[0]])
  })

  it('never matches a false boolean field, which renders as empty text', () => {
    const rows = [{ callsign: 'WRAB123', name: 'Sam', no_answer: false }]
    expect(filterRoster(rows, 'yes', ['callsign', 'name', 'no_answer'])).toEqual([])
  })
})

describe('sortRoster', () => {
  it('sorts ascending by a column', () => {
    expect(sortRoster(ROWS, 'callsign', 'asc').map((r) => r.callsign))
      .toEqual(['KD8ABC', 'KE8XYZ', 'WRAB123'])
  })

  it('sorts descending', () => {
    expect(sortRoster(ROWS, 'name', 'desc').map((r) => r.name))
      .toEqual(['Sam', 'Maria', 'Alex'])
  })

  it('does not mutate the input', () => {
    const copy = [...ROWS]
    sortRoster(ROWS, 'callsign', 'asc')
    expect(ROWS).toEqual(copy)
  })

  it('returns the original order for a null column', () => {
    expect(sortRoster(ROWS, null, 'asc')).toEqual(ROWS)
  })
})

describe('useRosterSort', () => {
  it('filters and sorts rows together', () => {
    const { result } = renderHook(() => useRosterSort(ROWS, KEYS))
    act(() => result.current.setRosterQuery('holland'))
    act(() => result.current.setSortColumn('name'))
    expect(result.current.visibleRoster.map((r) => r.name)).toEqual(['Alex', 'Maria'])
  })

  it('handleSort toggles direction on repeat clicks of the same column', () => {
    const { result } = renderHook(() => useRosterSort(ROWS, KEYS))
    act(() => result.current.handleSort('callsign'))
    expect(result.current.sortColumn).toBe('callsign')
    expect(result.current.sortDirection).toBe('asc')
    act(() => result.current.handleSort('callsign'))
    expect(result.current.sortDirection).toBe('desc')
  })

  it('handleSort resets to ascending when switching to a new column', () => {
    const { result } = renderHook(() => useRosterSort(ROWS, KEYS))
    act(() => result.current.handleSort('callsign'))
    act(() => result.current.handleSort('callsign'))
    expect(result.current.sortDirection).toBe('desc')
    act(() => result.current.handleSort('name'))
    expect(result.current.sortColumn).toBe('name')
    expect(result.current.sortDirection).toBe('asc')
  })

  it('showFilterInput is true once rows exceed the threshold', () => {
    const { result: few } = renderHook(() => useRosterSort(ROWS.slice(0, 2), KEYS))
    expect(few.current.showFilterInput).toBe(false)
    const { result: many } = renderHook(() => useRosterSort(ROWS, KEYS))
    expect(many.current.showFilterInput).toBe(true)
  })

  it('showFilterInput stays true once a query is typed, even if that query empties the roster below threshold', () => {
    // Regression for I5: a filter box that only appears when there are
    // "enough" rows must never disappear as a side effect of the filter
    // it controls thinning the visible rows below that threshold.
    const { result } = renderHook(() => useRosterSort(ROWS.slice(0, 2), KEYS))
    expect(result.current.showFilterInput).toBe(false)
    act(() => result.current.setRosterQuery('nobody'))
    expect(result.current.visibleRoster).toHaveLength(0)
    expect(result.current.showFilterInput).toBe(true)
  })

  it('clears query and sort when resetKey changes', () => {
    const { result, rerender } = renderHook(
      ({ resetKey }) => useRosterSort(ROWS, KEYS, resetKey),
      { initialProps: { resetKey: 'session-1' } },
    )
    act(() => {
      result.current.setRosterQuery('maria')
      result.current.setSortColumn('name')
    })
    expect(result.current.rosterQuery).toBe('maria')
    expect(result.current.sortColumn).toBe('name')

    rerender({ resetKey: 'session-2' })
    expect(result.current.rosterQuery).toBe('')
    expect(result.current.sortColumn).toBe(null)
  })
})
