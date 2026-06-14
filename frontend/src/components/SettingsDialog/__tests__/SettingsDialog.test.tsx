import React from 'react'
import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { SettingsDialog } from '../SettingsDialog'

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

const adminConfig = {
  stationCallsign: 'WSLZ233',
  stationName: 'Bob',
  stationLocation: 'Grand Rapids',
  stationVoice: '',
  stationLengthScale: 1,
  geminiApiKeySet: false,
  journalsDir: '',
  ncsZone: '',
  rxMode: 'voice',
}

const serverConfig = {
  vadThreshold: 0.5,
  whisperModel: 'small.en',
  whisperModelFinal: '',
  squelchAdaptive: false,
  sttDebugCapture: false,
  txConditioning: false,
  pttMode: 'manual',
  pttSerialPort: '',
  pttSerialLine: 'RTS',
  monitorPassthrough: false,
  attendanceEnabled: false,
  savedPhrases: [],
}

function makeProps(overrides: Record<string, unknown> = {}) {
  return {
    open: true,
    onClose: vi.fn(),
    adminConfig,
    voices: [],
    voicePreviewBusy: false,
    onAdminSave: vi.fn(),
    onPreviewVoice: vi.fn(),
    serverConfig,
    onServerConfigSave: vi.fn(),
    ...overrides,
  } as React.ComponentProps<typeof SettingsDialog>
}

describe('SettingsDialog', () => {
  it('renders Station and System tabs', () => {
    render(<SettingsDialog {...makeProps()} />)
    expect(screen.getByRole('tab', { name: 'Station' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'System' })).toBeInTheDocument()
  })

  it('shows the Station tab by default; its Save calls onAdminSave', () => {
    const onAdminSave = vi.fn()
    render(<SettingsDialog {...makeProps({ onAdminSave })} />)
    // Only the active (Station) tab's Save is accessible; the hidden System
    // tabpanel's Save is excluded from role queries.
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onAdminSave).toHaveBeenCalledTimes(1)
  })

  it('switching to the System tab and saving calls onServerConfigSave only', () => {
    const onAdminSave = vi.fn()
    const onServerConfigSave = vi.fn()
    render(<SettingsDialog {...makeProps({ onAdminSave, onServerConfigSave })} />)
    fireEvent.click(screen.getByRole('tab', { name: 'System' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onServerConfigSave).toHaveBeenCalledTimes(1)
    expect(onAdminSave).not.toHaveBeenCalled()
  })

  it('Close button calls onClose', () => {
    const onClose = vi.fn()
    render(<SettingsDialog {...makeProps({ onClose })} />)
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders the provided users panel on the Station tab', () => {
    render(<SettingsDialog {...makeProps({ usersPanel: <div>USERS_PANEL_MARKER</div> })} />)
    expect(screen.getByText('USERS_PANEL_MARKER')).toBeInTheDocument()
  })
})
