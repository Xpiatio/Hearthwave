import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { SettingsDialog } from '../SettingsDialog'

function makeProps(overrides = {}) {
  return {
    open: true, onClose: vi.fn(), isAdmin: true,
    filterProfanity: false, fuzzyCallsign: false, inputDevice: -1, systemMonitorSink: '',
    inputDevices: [], monitorSinks: [], outputDevice: -1, outputDevices: [],
    spectroColormap: 'viridis' as const, spectroFreqRange: 'full' as const, spectroTimeWindowS: 30,
    onToggleProfanity: vi.fn(), onToggleFuzzy: vi.fn(), onInputDeviceChange: vi.fn(),
    onOutputDeviceChange: vi.fn(), onSpectroColormapChange: vi.fn(),
    onSpectroFreqRangeChange: vi.fn(), onSpectroTimeWindowChange: vi.fn(),
    adminConfig: {
      stationCallsign: 'N0CALL', stationName: '', stationLocation: '', stationVoice: '',
      stationLengthScale: 1, geminiApiKeySet: false, journalsDir: '', ncsZone: '', rxMode: 'voice',
    },
    voices: [], voicePreviewBusy: false, onAdminSave: vi.fn(), onPreviewVoice: vi.fn(),
    serverConfig: {
      vadThreshold: 0.5, whisperModel: 'base', whisperModelFinal: '', squelchAdaptive: false,
      sttDebugCapture: false, txConditioning: false, voxPrimerEnabled: false, voxPrimerMs: 0,
      voxPrimerWordEnabled: false, voxPrimerWord: '', pttMode: 'manual', pttSerialPort: '',
      pttSerialLine: 'RTS', monitorPassthrough: false, attendanceEnabled: false, savedPhrases: [],
      meshcoreEnabled: false, meshcoreSerialPort: '', meshcoreBaud: 115200,
      meshcoreMaxPacketLength: 180, meshcorePrefixSeparator: ': ', meshcoreChannelIdx: 0,
      meshtasticEnabled: false, meshtasticSerialPort: '', meshtasticMaxPacketLength: 200,
      meshtasticPrefixSeparator: ': ', meshtasticChannelIdx: 0, ncsEnabled: true,
    },
    onServerConfigSave: vi.fn(), onRescanVocabulary: vi.fn(),
    plugins: [], onPluginsSave: vi.fn(),
    ...overrides,
  }
}

describe('SettingsDialog', () => {
  it('shows all admin tabs', () => {
    render(<SettingsDialog {...makeProps()} />)
    expect(screen.getByRole('tab', { name: 'Preferences' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Station' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'System' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Plugins' })).toBeInTheDocument()
  })

  it('shows only Preferences for a non-admin (no tab bar)', () => {
    render(<SettingsDialog {...makeProps({ isAdmin: false })} />)
    expect(screen.queryByRole('tab', { name: 'Station' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'System' })).not.toBeInTheDocument()
  })

  it('disables Save until something changes, then applies a preference on Save and stays open', async () => {
    const onToggleProfanity = vi.fn(); const onClose = vi.fn()
    render(<SettingsDialog {...makeProps({ onToggleProfanity, onClose })} />)
    const save = screen.getByRole('button', { name: /^save$/i })
    expect(save).toBeDisabled()
    await userEvent.click(screen.getByText('Profanity Filter'))
    expect(save).toBeEnabled()
    await userEvent.click(save)
    expect(onToggleProfanity).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()        // stays open
    expect(screen.getByText(/settings saved/i)).toBeInTheDocument()
  })

  it('titles the dialog "Settings"', () => {
    render(<SettingsDialog {...makeProps()} />)
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  describe('discard-guard on Close', () => {
    it('does NOT call window.confirm when closing a clean (unmodified) dialog', async () => {
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
      render(<SettingsDialog {...makeProps()} />)
      await userEvent.click(screen.getByRole('button', { name: /^close$/i }))
      expect(confirm).not.toHaveBeenCalled()
    })

    it('calls window.confirm when closing a dirty dialog', async () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false)
      render(<SettingsDialog {...makeProps()} />)
      await userEvent.click(screen.getByText('Profanity Filter'))
      await userEvent.click(screen.getByRole('button', { name: /^close$/i }))
      expect(window.confirm).toHaveBeenCalledTimes(1)
    })

    it('does NOT call onClose when dirty and confirm returns false', async () => {
      const onClose = vi.fn()
      vi.spyOn(window, 'confirm').mockReturnValue(false)
      render(<SettingsDialog {...makeProps({ onClose })} />)
      await userEvent.click(screen.getByText('Profanity Filter'))
      await userEvent.click(screen.getByRole('button', { name: /^close$/i }))
      expect(onClose).not.toHaveBeenCalled()
    })

    it('DOES call onClose when dirty and confirm returns true', async () => {
      const onClose = vi.fn()
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      render(<SettingsDialog {...makeProps({ onClose })} />)
      await userEvent.click(screen.getByText('Profanity Filter'))
      await userEvent.click(screen.getByRole('button', { name: /^close$/i }))
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  it('footer Save commits a dirty Station tab (via admin ref) without closing', async () => {
    const onAdminSave = vi.fn()
    render(<SettingsDialog {...makeProps({ onAdminSave })} />)
    // Switch to Station tab
    await userEvent.click(screen.getByRole('tab', { name: 'Station' }))
    // Modify Station Name to make AdminPanel dirty
    const nameField = screen.getByLabelText(/station name/i)
    await userEvent.clear(nameField)
    await userEvent.type(nameField, 'New Name')
    // Click footer Save
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(onAdminSave).toHaveBeenCalledTimes(1)
  })
})
