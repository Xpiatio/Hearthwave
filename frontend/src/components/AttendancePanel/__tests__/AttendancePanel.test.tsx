import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { AttendancePanel } from '../AttendancePanel'
import type { AttendanceStation } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const STATIONS: AttendanceStation[] = [
  { callsign: 'W1AAA', name: 'Alice', location: 'Grand Rapids', gmrs: 'WRXX123', ham: 'W1AAA' },
  { callsign: 'KD9ZZZ', name: 'Bob', location: 'Holland', gmrs: '', ham: 'KD9ZZZ' },
]

describe('AttendancePanel', () => {
  describe('empty state', () => {
    it('renders heading', () => {
      render(<AttendancePanel stations={[]} onClear={vi.fn()} />)
      expect(screen.getByText('STATIONS HEARD THIS SESSION')).toBeInTheDocument()
    })

    it('renders empty message', () => {
      render(<AttendancePanel stations={[]} onClear={vi.fn()} />)
      expect(screen.getByText('No stations heard yet.')).toBeInTheDocument()
    })

    it('CLEAR button is disabled when stations list is empty', () => {
      render(<AttendancePanel stations={[]} onClear={vi.fn()} />)
      expect(screen.getByRole('button', { name: /clear/i })).toBeDisabled()
    })

    it('does not render table when no stations', () => {
      render(<AttendancePanel stations={[]} onClear={vi.fn()} />)
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
    })
  })

  describe('with stations', () => {
    it('does not render the empty message', () => {
      render(<AttendancePanel stations={STATIONS} onClear={vi.fn()} />)
      expect(screen.queryByText('No stations heard yet.')).not.toBeInTheDocument()
    })

    it('renders table with column headers', () => {
      render(<AttendancePanel stations={STATIONS} onClear={vi.fn()} />)
      expect(screen.getByRole('table')).toBeInTheDocument()
      expect(screen.getByText('Callsign')).toBeInTheDocument()
      expect(screen.getByText('Name')).toBeInTheDocument()
      expect(screen.getByText('Location')).toBeInTheDocument()
      expect(screen.getByText('GMRS')).toBeInTheDocument()
      expect(screen.getByText('HAM')).toBeInTheDocument()
    })

    it('renders a row for each station', () => {
      render(<AttendancePanel stations={STATIONS} onClear={vi.fn()} />)
      expect(screen.getAllByText('W1AAA').length).toBeGreaterThan(0)
      expect(screen.getByText('Alice')).toBeInTheDocument()
      expect(screen.getByText('Grand Rapids')).toBeInTheDocument()
      expect(screen.getByText('WRXX123')).toBeInTheDocument()
      expect(screen.getAllByText('KD9ZZZ').length).toBeGreaterThan(0)
      expect(screen.getByText('Bob')).toBeInTheDocument()
      expect(screen.getByText('Holland')).toBeInTheDocument()
    })

    it('CLEAR button is enabled when stations are present', () => {
      render(<AttendancePanel stations={STATIONS} onClear={vi.fn()} />)
      expect(screen.getByRole('button', { name: /clear/i })).toBeEnabled()
    })

    it('calls onClear when CLEAR button is clicked', () => {
      const onClear = vi.fn()
      render(<AttendancePanel stations={STATIONS} onClear={onClear} />)
      fireEvent.click(screen.getByRole('button', { name: /clear/i }))
      expect(onClear).toHaveBeenCalledTimes(1)
    })

    it('onClear is NOT called when button is disabled (empty list)', () => {
      const onClear = vi.fn()
      render(<AttendancePanel stations={[]} onClear={onClear} />)
      fireEvent.click(screen.getByRole('button', { name: /clear/i }))
      expect(onClear).not.toHaveBeenCalled()
    })

    it('renders all stations passed in', () => {
      const single: AttendanceStation[] = [
        { callsign: 'N0CALL', name: 'Test', location: 'Nowhere', gmrs: 'WNXX999', ham: '' },
      ]
      render(<AttendancePanel stations={single} onClear={vi.fn()} />)
      expect(screen.getByText('N0CALL')).toBeInTheDocument()
      expect(screen.getByText('Test')).toBeInTheDocument()
    })
  })
})
