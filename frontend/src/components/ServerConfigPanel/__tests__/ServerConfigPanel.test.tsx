import { render as rtlRender, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ServerConfigPanel } from '../ServerConfigPanel'
import type { ServerConfig } from '../ServerConfigPanel'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

function makeConfig(overrides: Partial<ServerConfig> = {}): ServerConfig {
  return {
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
    ...overrides,
  }
}

function makeDefaultProps(overrides: Partial<ServerConfig> = {}) {
  return {
    open: true,
    onClose: vi.fn(),
    config: makeConfig(overrides),
    onSave: vi.fn(),
  }
}

describe('ServerConfigPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Rendering (dialog open)
  // -------------------------------------------------------------------------

  it('renders the dialog when open=true', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Server Config')).toBeInTheDocument()
  })

  it('does not render dialog content when open=false', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} open={false} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders Whisper Model select', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/whisper model/i)).toBeInTheDocument()
  })

  it('renders VAD sensitivity slider', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('slider', { name: /vad sensitivity/i })).toBeInTheDocument()
  })

  it('renders PTT Mode select', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/ptt mode/i)).toBeInTheDocument()
  })

  it('renders Monitor passthrough switch', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/monitor passthrough/i)).toBeInTheDocument()
  })

  it('renders Attendance tracking switch', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/attendance tracking/i)).toBeInTheDocument()
  })

  it('renders Cancel and Save buttons', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Initial values loaded from config
  // -------------------------------------------------------------------------

  it('initializes with config values when dialog opens', () => {
    render(
      <ServerConfigPanel
        {...makeDefaultProps({ vadThreshold: 0.7, whisperModel: 'medium.en' })}
      />
    )
    // Slider aria-valuenow reflects the VAD threshold
    const slider = screen.getByRole('slider', { name: /vad sensitivity/i })
    expect(slider).toHaveAttribute('aria-valuenow', '0.7')
  })

  it('shows monitorPassthrough as checked when config.monitorPassthrough=true', () => {
    render(<ServerConfigPanel {...makeDefaultProps({ monitorPassthrough: true })} />)
    expect(screen.getByLabelText(/monitor passthrough/i)).toBeChecked()
  })

  it('shows attendanceEnabled as checked when config.attendanceEnabled=true', () => {
    render(<ServerConfigPanel {...makeDefaultProps({ attendanceEnabled: true })} />)
    expect(screen.getByLabelText(/attendance tracking/i)).toBeChecked()
  })

  // -------------------------------------------------------------------------
  // Conditional serial port fields
  // -------------------------------------------------------------------------

  it('does NOT show serial port fields when pttMode is "manual"', () => {
    render(<ServerConfigPanel {...makeDefaultProps({ pttMode: 'manual' })} />)
    expect(screen.queryByLabelText(/serial port/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/ptt line/i)).not.toBeInTheDocument()
  })

  it('does NOT show serial port fields when pttMode is "vox"', () => {
    render(<ServerConfigPanel {...makeDefaultProps({ pttMode: 'vox' })} />)
    expect(screen.queryByLabelText(/serial port/i)).not.toBeInTheDocument()
  })

  it('shows serial port and PTT line fields when pttMode is "serial"', () => {
    render(<ServerConfigPanel {...makeDefaultProps({ pttMode: 'serial' })} />)
    expect(screen.getByLabelText(/serial port/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/ptt line/i)).toBeInTheDocument()
  })

  it('renders serial port value from config when pttMode=serial', () => {
    render(
      <ServerConfigPanel
        {...makeDefaultProps({ pttMode: 'serial', pttSerialPort: '/dev/ttyUSB0' })}
      />
    )
    expect(screen.getByDisplayValue('/dev/ttyUSB0')).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Changing PTT mode exposes / hides serial fields
  // -------------------------------------------------------------------------

  it('shows serial fields after switching PTT mode from manual to serial', async () => {
    const user = userEvent.setup()
    render(<ServerConfigPanel {...makeDefaultProps({ pttMode: 'manual' })} />)

    await user.click(screen.getByLabelText(/ptt mode/i))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText(/serial port/i))

    expect(screen.getByLabelText(/serial port/i)).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Cancel closes dialog
  // -------------------------------------------------------------------------

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<ServerConfigPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(props.onClose).toHaveBeenCalledTimes(1)
  })

  // -------------------------------------------------------------------------
  // Save callback
  // -------------------------------------------------------------------------

  it('calls onSave and onClose with correct values when Save is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({
      vadThreshold: 0.3,
      whisperModel: 'base.en',
      pttMode: 'manual',
      pttSerialPort: '  ',
      pttSerialLine: 'RTS',
      monitorPassthrough: true,
      attendanceEnabled: true,
    })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledTimes(1)
    expect(props.onSave).toHaveBeenCalledWith({
      vad_threshold: 0.3,
      whisper_model: 'base.en',
      whisper_model_final: '',
      squelch_adaptive: false,
      stt_debug_capture: false,
      tx_conditioning: false,
      ptt_mode: 'manual',
      ptt_serial_port: '', // trimmed
      ptt_serial_line: 'RTS',
      monitor_passthrough: true,
      attendance_enabled: true,
      saved_phrases: [],
    })
    expect(props.onClose).toHaveBeenCalledTimes(1)
  })

  it('trims whitespace from serial port before saving', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ pttMode: 'serial', pttSerialPort: '  /dev/ttyUSB0  ' })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ ptt_serial_port: '/dev/ttyUSB0' })
    )
  })

  // -------------------------------------------------------------------------
  // Monitor passthrough toggle
  // -------------------------------------------------------------------------

  it('toggles monitorPassthrough state when switch is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ monitorPassthrough: false })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/monitor passthrough/i))

    // Now save — should see monitor_passthrough: true
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ monitor_passthrough: true })
    )
  })

  // -------------------------------------------------------------------------
  // Attendance toggle
  // -------------------------------------------------------------------------

  it('toggles attendanceEnabled state when switch is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ attendanceEnabled: false })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/attendance tracking/i))

    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ attendance_enabled: true })
    )
  })

  // -------------------------------------------------------------------------
  // Whisper model change
  // -------------------------------------------------------------------------

  it('passes newly selected whisper model to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ whisperModel: 'small.en' })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/whisper model/i))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText(/medium\.en/i))

    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ whisper_model: 'medium.en' })
    )
  })

  // -------------------------------------------------------------------------
  // Re-initialization on open
  // -------------------------------------------------------------------------

  it('re-initializes form when dialog is re-opened', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <ThemeProvider theme={makeTheme(false)}>
        <ServerConfigPanel
          open={false}
          onClose={vi.fn()}
          config={makeConfig({ monitorPassthrough: false })}
          onSave={vi.fn()}
        />
      </ThemeProvider>
    )

    // Open the dialog
    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <ServerConfigPanel
          open={true}
          onClose={vi.fn()}
          config={makeConfig({ monitorPassthrough: true })}
          onSave={vi.fn()}
        />
      </ThemeProvider>
    )

    // Config value (true) should be reflected
    expect(screen.getByLabelText(/monitor passthrough/i)).toBeChecked()
  })

  // -------------------------------------------------------------------------
  // Two-tier final-pass model
  // -------------------------------------------------------------------------

  it('renders the final-pass model select', () => {
    render(<ServerConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/final-pass model/i)).toBeInTheDocument()
  })

  it('defaults the final-pass model to Off when empty', () => {
    render(<ServerConfigPanel {...makeDefaultProps({ whisperModelFinal: '' })} />)
    // The combobox display shows the "Off" label for the empty value.
    expect(screen.getByRole('combobox', { name: /final-pass model/i })).toHaveTextContent(/off/i)
  })

  it('passes the selected final-pass model to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ whisperModelFinal: '' })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/final-pass model/i))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText(/distil-large-v3/i))

    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ whisper_model_final: 'distil-large-v3' })
    )
  })

  // -------------------------------------------------------------------------
  // New STT/TX toggles
  // -------------------------------------------------------------------------

  it('toggles adaptive squelch and passes it to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ squelchAdaptive: false })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/adaptive squelch/i))
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ squelch_adaptive: true })
    )
  })

  it('toggles TX conditioning and passes it to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ txConditioning: false })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/tx conditioning/i))
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ tx_conditioning: true })
    )
  })

  it('toggles debug capture and passes it to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ sttDebugCapture: false })
    render(<ServerConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/debug capture/i))
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ stt_debug_capture: true })
    )
  })

  it('reflects config values for the new toggles', () => {
    render(
      <ServerConfigPanel
        {...makeDefaultProps({ squelchAdaptive: true, txConditioning: true, sttDebugCapture: true })}
      />
    )
    expect(screen.getByLabelText(/adaptive squelch/i)).toBeChecked()
    expect(screen.getByLabelText(/tx conditioning/i)).toBeChecked()
    expect(screen.getByLabelText(/debug capture/i)).toBeChecked()
  })

  // -------------------------------------------------------------------------
  // VOX primer
  // -------------------------------------------------------------------------

  it('saves vox_primer_enabled when toggled on', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ voxPrimerEnabled: false, voxPrimerMs: 300 })
    render(<ServerConfigPanel {...props} embedded open onClose={() => {}} />)

    await user.click(screen.getByLabelText(/vox primer tone/i))
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ vox_primer_enabled: true, vox_primer_ms: 300 })
    )
  })
})
