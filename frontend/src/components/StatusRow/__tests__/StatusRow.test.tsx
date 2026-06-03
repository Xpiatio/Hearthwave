import { render as rtlRender, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect } from 'vitest'
import { StatusRow } from '../StatusRow'
import type { StatusMsg } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const STATUS_ALL_OK: StatusMsg = {
  type: 'status',
  radio_connected: true,
  volume_ok: true,
  channel_clear: true,
}

const STATUS_ALL_ERROR: StatusMsg = {
  type: 'status',
  radio_connected: false,
  volume_ok: false,
  channel_clear: false,
}

const STATUS_MIXED: StatusMsg = {
  type: 'status',
  radio_connected: true,
  volume_ok: false,
  channel_clear: true,
}

describe('StatusRow', () => {
  describe('null status (checking)', () => {
    it('renders radio hardware status container', () => {
      render(<StatusRow status={null} />)
      expect(screen.getByRole('status', { name: /radio hardware status/i })).toBeInTheDocument()
    })

    it('shows checking labels for all three tiles', () => {
      render(<StatusRow status={null} />)
      expect(screen.getByText('Radio Cable: Checking...')).toBeInTheDocument()
      expect(screen.getByText('Radio Volume: Checking...')).toBeInTheDocument()
      expect(screen.getByText('Channel: Checking...')).toBeInTheDocument()
    })

    it('uses checking aria-labels', () => {
      render(<StatusRow status={null} />)
      expect(screen.getByLabelText('Radio cable status: checking')).toBeInTheDocument()
      expect(screen.getByLabelText('Radio volume status: checking')).toBeInTheDocument()
      expect(screen.getByLabelText('Channel status: checking')).toBeInTheDocument()
    })
  })

  describe('all ok status', () => {
    it('renders connected/perfect/clear labels', () => {
      render(<StatusRow status={STATUS_ALL_OK} />)
      expect(screen.getByText('Radio Cable Connected')).toBeInTheDocument()
      expect(screen.getByText('Radio Volume is Perfect')).toBeInTheDocument()
      expect(screen.getByText('Channel: Clear')).toBeInTheDocument()
    })

    it('uses connected aria-labels', () => {
      render(<StatusRow status={STATUS_ALL_OK} />)
      expect(screen.getByLabelText('Radio cable: connected')).toBeInTheDocument()
      expect(screen.getByLabelText('Radio volume: perfect')).toBeInTheDocument()
      expect(screen.getByLabelText('Channel: clear')).toBeInTheDocument()
    })
  })

  describe('all error status', () => {
    it('renders error labels', () => {
      render(<StatusRow status={STATUS_ALL_ERROR} />)
      expect(screen.getByText('Radio Cable Disconnected')).toBeInTheDocument()
      expect(screen.getByText('Radio Volume Needs Adjustment')).toBeInTheDocument()
      expect(screen.getByText('Channel: Busy')).toBeInTheDocument()
    })

    it('uses error aria-labels', () => {
      render(<StatusRow status={STATUS_ALL_ERROR} />)
      expect(screen.getByLabelText('Radio cable: disconnected')).toBeInTheDocument()
      expect(screen.getByLabelText('Radio volume: needs adjustment')).toBeInTheDocument()
      expect(screen.getByLabelText('Channel: busy')).toBeInTheDocument()
    })
  })

  describe('mixed status', () => {
    it('renders mixed state labels correctly', () => {
      render(<StatusRow status={STATUS_MIXED} />)
      expect(screen.getByText('Radio Cable Connected')).toBeInTheDocument()
      expect(screen.getByText('Radio Volume Needs Adjustment')).toBeInTheDocument()
      expect(screen.getByText('Channel: Clear')).toBeInTheDocument()
    })

    it('uses correct aria-labels for mixed state', () => {
      render(<StatusRow status={STATUS_MIXED} />)
      expect(screen.getByLabelText('Radio cable: connected')).toBeInTheDocument()
      expect(screen.getByLabelText('Radio volume: needs adjustment')).toBeInTheDocument()
      expect(screen.getByLabelText('Channel: clear')).toBeInTheDocument()
    })
  })

  it('renders exactly 3 tiles (one per hardware status)', () => {
    render(<StatusRow status={STATUS_ALL_OK} />)
    // Each tile has a unique aria-label; verify all 3 are present
    expect(screen.getByLabelText('Radio cable: connected')).toBeInTheDocument()
    expect(screen.getByLabelText('Radio volume: perfect')).toBeInTheDocument()
    expect(screen.getByLabelText('Channel: clear')).toBeInTheDocument()
  })
})
