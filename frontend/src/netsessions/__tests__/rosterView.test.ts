import { describe, it, expect } from 'vitest'
import { filterRoster, sortRoster } from '../rosterView'

const ROWS = [
  { callsign: 'WRAB123', name: 'Sam', location: 'Zeeland' },
  { callsign: 'KD8ABC', name: 'Maria', location: 'Holland' },
  { callsign: 'KE8XYZ', name: 'Alex', location: 'Holland' },
]

describe('filterRoster', () => {
  it('returns every row for a blank query', () => {
    expect(filterRoster(ROWS, '')).toHaveLength(3)
  })

  it('matches a callsign case-insensitively', () => {
    expect(filterRoster(ROWS, 'kd8')).toEqual([ROWS[1]])
  })

  it('matches any string field', () => {
    expect(filterRoster(ROWS, 'holland')).toHaveLength(2)
  })

  it('returns nothing when no row matches', () => {
    expect(filterRoster(ROWS, 'nobody')).toEqual([])
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
