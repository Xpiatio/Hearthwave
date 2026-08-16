import { render, screen, within } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { NetRosterSheet } from '../NetRosterSheet'
import type { NetSessionDetail } from '../../../types/ws'

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
      callsign: 'WRAB123', name: 'Sam', location: 'Zeeland',
      status: 'Standby', traffic: null,
      checkin_time: '2026-08-01T19:03:00Z', verified: false,
      via: 'radio', no_answer: true,
    },
  ],
}

const NOW = new Date('2026-08-01T20:05:00Z')

/** The sheet's data rows, header row excluded. */
function bodyRows(): HTMLElement[] {
  return screen.getAllByRole('row').slice(1)
}

describe('NetRosterSheet', () => {
  it('heads the sheet with the net type and date', () => {
    render(<NetRosterSheet session={SESSION} now={NOW} />)
    expect(screen.getByRole('heading')).toHaveTextContent('Neighborhood net — 2026-08-01')
  })

  it('summarises the operational period above the roster', () => {
    render(<NetRosterSheet session={SESSION} now={NOW} />)
    expect(screen.getByTestId('sheet-meta')).toHaveTextContent('52 min')
    expect(screen.getByTestId('sheet-meta')).toHaveTextContent('2 check-ins')
  })

  it('writes one numbered row per check-in, in check-in order', () => {
    render(<NetRosterSheet session={{ ...SESSION, roster: [SESSION.roster[1], SESSION.roster[0]] }} now={NOW} />)
    const rows = bodyRows()
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('1')).toBeInTheDocument()
    expect(within(rows[0]).getByText('KD8ABC')).toBeInTheDocument()
    expect(within(rows[0]).getByText('19:01')).toBeInTheDocument()
    expect(within(rows[1]).getByText('WRAB123')).toBeInTheDocument()
  })

  it('carries name, location and traffic across for a plain check-in', () => {
    render(<NetRosterSheet session={SESSION} now={NOW} />)
    const row = bodyRows()[0]
    expect(within(row).getByText('Maria')).toBeInTheDocument()
    expect(within(row).getByText('Holland')).toBeInTheDocument()
    expect(within(row).getByText('Routine')).toBeInTheDocument()
    // A routine check-in has nothing worth noting.
    expect(within(row).getByTestId('sheet-notes')).toBeEmptyDOMElement()
  })

  it('folds a non-default status, a radio check-in and a no-answer into Notes', () => {
    render(<NetRosterSheet session={SESSION} now={NOW} />)
    const notes = within(bodyRows()[1]).getByTestId('sheet-notes')
    expect(notes).toHaveTextContent('Standby')
    expect(notes).toHaveTextContent('by radio')
    expect(notes).toHaveTextContent('no answer when called')
  })

  it('says so plainly when nobody checked in', () => {
    render(<NetRosterSheet session={{ ...SESSION, roster: [] }} now={NOW} />)
    expect(screen.getByText(/no check-ins recorded/i)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('leaves a hand-signed sign-off and records when it was printed', () => {
    render(<NetRosterSheet session={SESSION} now={NOW} />)
    expect(screen.getByText(/prepared by/i)).toBeInTheDocument()
    expect(screen.getByText(/printed 2026-08-01 20:05/i)).toBeInTheDocument()
  })

  it('carries the class the print stylesheet hooks onto', () => {
    const { container } = render(<NetRosterSheet session={SESSION} now={NOW} />)
    expect(container.firstChild).toHaveClass('net-roster-sheet')
  })
})
