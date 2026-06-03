import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { PendingStationsBar } from '../PendingStationsBar'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const STATIONS = [
  { callsign: 'W1AAA', name: 'Alice', location: 'Grand Rapids' },
  { callsign: 'KD9ZZZ', name: '', location: '' },
]

describe('PendingStationsBar', () => {
  describe('empty state', () => {
    it('renders nothing when stations list is empty', () => {
      const { container } = render(
        <PendingStationsBar
          stations={[]}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      expect(container.firstChild).toBeNull()
    })
  })

  describe('with stations', () => {
    it('renders the unrecognized section', () => {
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      expect(screen.getByRole('region', { name: /unrecognized stations/i })).toBeInTheDocument()
    })

    it('renders a chip for each station', () => {
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      expect(screen.getByText('W1AAA')).toBeInTheDocument()
      expect(screen.getByText('KD9ZZZ')).toBeInTheDocument()
    })

    it('chip aria-label includes details when name/location present', () => {
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      expect(
        screen.getByRole('button', { name: /Add W1AAA to contacts — Alice, Grand Rapids/i })
      ).toBeInTheDocument()
    })

    it('chip aria-label without details when name and location are empty', () => {
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      expect(
        screen.getByRole('button', { name: 'Add KD9ZZZ to contacts' })
      ).toBeInTheDocument()
    })

    it('renders "Dismiss All" button', () => {
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /dismiss all unrecognized stations/i })).toBeInTheDocument()
    })

    it('calls onAdd with the correct station when chip is clicked', () => {
      const onAdd = vi.fn()
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={onAdd}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      fireEvent.click(screen.getByRole('button', { name: /Add W1AAA to contacts/i }))
      expect(onAdd).toHaveBeenCalledTimes(1)
      expect(onAdd).toHaveBeenCalledWith(STATIONS[0])
    })

    it('calls onDismiss with the correct callsign when delete icon is clicked', () => {
      const onDismiss = vi.fn()
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={onDismiss}
          onDismissAll={vi.fn()}
        />
      )
      fireEvent.click(screen.getByLabelText('Dismiss W1AAA'))
      expect(onDismiss).toHaveBeenCalledTimes(1)
      expect(onDismiss).toHaveBeenCalledWith('W1AAA')
    })

    it('calls onDismissAll when "Dismiss All" button is clicked', () => {
      const onDismissAll = vi.fn()
      render(
        <PendingStationsBar
          stations={STATIONS}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={onDismissAll}
        />
      )
      fireEvent.click(screen.getByRole('button', { name: /dismiss all unrecognized stations/i }))
      expect(onDismissAll).toHaveBeenCalledTimes(1)
    })

    it('handles a station with name but no location', () => {
      const stations = [{ callsign: 'N0CALL', name: 'Dave', location: '' }]
      render(
        <PendingStationsBar
          stations={stations}
          onAdd={vi.fn()}
          onDismiss={vi.fn()}
          onDismissAll={vi.fn()}
        />
      )
      // details should just be the name without trailing comma
      expect(
        screen.getByRole('button', { name: 'Add N0CALL to contacts — Dave' })
      ).toBeInTheDocument()
    })
  })
})
