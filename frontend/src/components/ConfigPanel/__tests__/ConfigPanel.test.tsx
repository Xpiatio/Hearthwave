import { render as rtlRender, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ConfigPanel } from '../ConfigPanel'
import type { InputDeviceOption, MonitorSinkOption } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const DEVICE_OPTIONS: InputDeviceOption[] = [
  { label: 'Built-in Microphone', id: 0 },
  { label: 'USB Audio Device', id: 1 },
  { label: 'System Audio Output (loopback)', id: 'system_monitor' },
]

const SINK_OPTIONS: MonitorSinkOption[] = [
  { label: 'Built-in Speakers', sink_id: 'sink1' },
  { label: 'HDMI Audio', sink_id: 'sink2' },
]

function makeDefaultProps() {
  return {
    filterProfanity: false,
    fuzzyCallsign: false,
    inputDevice: 0 as string | number,
    systemMonitorSink: '',
    inputDevices: DEVICE_OPTIONS,
    monitorSinks: SINK_OPTIONS,
    spectroColormap: 'viridis' as const,
    spectroFreqRange: 'voice' as const,
    spectroTimeWindowS: 30,
    onToggleProfanity: vi.fn(),
    onToggleFuzzy: vi.fn(),
    onInputDeviceChange: vi.fn(),
    onSpectroColormapChange: vi.fn(),
    onSpectroFreqRangeChange: vi.fn(),
    onSpectroTimeWindowChange: vi.fn(),
  }
}

describe('ConfigPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it('renders without crashing', () => {
    const props = makeDefaultProps()
    render(<ConfigPanel {...props} />)
    expect(screen.getByRole('region', { name: /configuration/i })).toBeInTheDocument()
  })

  it('displays the Configuration heading', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByText('Configuration')).toBeInTheDocument()
  })

  it('renders Profanity Filter switch', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText('Profanity Filter')).toBeInTheDocument()
  })

  it('renders Fuzzy Callsign Match switch', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText('Fuzzy Callsign Match')).toBeInTheDocument()
  })

  it('renders the Audio Input select', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/audio input/i)).toBeInTheDocument()
  })

  it('renders spectrogram colormap toggle buttons', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('group', { name: /spectrogram colormap/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /viridis/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /grayscale/i })).toBeInTheDocument()
  })

  it('renders spectrogram frequency range toggle buttons', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('group', { name: /spectrogram frequency range/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /voice band/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /full band/i })).toBeInTheDocument()
  })

  it('renders spectrogram time window toggle buttons', () => {
    render(<ConfigPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('group', { name: /spectrogram time window/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /10 second/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /30 second/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /60 second/i })).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Switch checked state
  // -------------------------------------------------------------------------

  it('reflects filterProfanity=true on the switch', () => {
    render(<ConfigPanel {...makeDefaultProps()} filterProfanity={true} />)
    const sw = screen.getByLabelText('Profanity Filter')
    expect(sw).toBeChecked()
  })

  it('reflects filterProfanity=false on the switch', () => {
    render(<ConfigPanel {...makeDefaultProps()} filterProfanity={false} />)
    const sw = screen.getByLabelText('Profanity Filter')
    expect(sw).not.toBeChecked()
  })

  it('reflects fuzzyCallsign=true on the switch', () => {
    render(<ConfigPanel {...makeDefaultProps()} fuzzyCallsign={true} />)
    const sw = screen.getByLabelText('Fuzzy Callsign Match')
    expect(sw).toBeChecked()
  })

  // -------------------------------------------------------------------------
  // Callbacks: toggles
  // -------------------------------------------------------------------------

  it('calls onToggleProfanity when profanity filter switch is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<ConfigPanel {...props} />)
    await user.click(screen.getByLabelText('Profanity Filter'))
    expect(props.onToggleProfanity).toHaveBeenCalledTimes(1)
  })

  it('calls onToggleFuzzy when fuzzy callsign switch is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<ConfigPanel {...props} />)
    await user.click(screen.getByLabelText('Fuzzy Callsign Match'))
    expect(props.onToggleFuzzy).toHaveBeenCalledTimes(1)
  })

  // -------------------------------------------------------------------------
  // Callbacks: spectrogram controls
  // -------------------------------------------------------------------------

  it('calls onSpectroColormapChange with "grayscale" when Grayscale button is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps() // current colormap = viridis
    render(<ConfigPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /grayscale colormap/i }))
    expect(props.onSpectroColormapChange).toHaveBeenCalledWith('grayscale')
  })

  it('does not call onSpectroColormapChange when the already-selected button is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps() // current colormap = viridis
    render(<ConfigPanel {...props} />)
    // clicking the already-selected toggle emits null, which the handler ignores
    await user.click(screen.getByRole('button', { name: /viridis colormap/i }))
    expect(props.onSpectroColormapChange).not.toHaveBeenCalled()
  })

  it('calls onSpectroFreqRangeChange with "full" when Full button is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps() // current range = voice
    render(<ConfigPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /full band/i }))
    expect(props.onSpectroFreqRangeChange).toHaveBeenCalledWith('full')
  })

  it('calls onSpectroTimeWindowChange with 60 when 60s button is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps() // current window = 30
    render(<ConfigPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /60 second/i }))
    expect(props.onSpectroTimeWindowChange).toHaveBeenCalledWith(60)
  })

  it('calls onSpectroTimeWindowChange with 10 when 10s button is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<ConfigPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /10 second/i }))
    expect(props.onSpectroTimeWindowChange).toHaveBeenCalledWith(10)
  })

  // -------------------------------------------------------------------------
  // Audio input device selector
  // -------------------------------------------------------------------------

  it('calls onInputDeviceChange with numeric id when a non-loopback device is selected', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<ConfigPanel {...props} />)

    // Open the select
    await user.click(screen.getByLabelText(/audio input/i))
    // Pick "USB Audio Device" (id: 1)
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText('USB Audio Device'))

    expect(props.onInputDeviceChange).toHaveBeenCalledWith(1, '')
  })

  it('calls onInputDeviceChange with "system_monitor" and current sink when loopback selected', async () => {
    const user = userEvent.setup()
    const props = { ...makeDefaultProps(), systemMonitorSink: 'sink1' }
    render(<ConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/audio input/i))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText('System Audio Output (loopback)'))

    expect(props.onInputDeviceChange).toHaveBeenCalledWith('system_monitor', 'sink1')
  })

  // -------------------------------------------------------------------------
  // Conditional: monitor sink selector
  // -------------------------------------------------------------------------

  it('does NOT render the Output Sink select when inputDevice is not system_monitor', () => {
    render(<ConfigPanel {...makeDefaultProps()} inputDevice={0} />)
    expect(screen.queryByLabelText(/output sink/i)).not.toBeInTheDocument()
  })

  it('renders the Output Sink select when inputDevice is system_monitor and sinks are available', () => {
    render(
      <ConfigPanel
        {...makeDefaultProps()}
        inputDevice="system_monitor"
        monitorSinks={SINK_OPTIONS}
      />
    )
    expect(screen.getByLabelText(/output sink/i)).toBeInTheDocument()
  })

  it('does NOT render the Output Sink select when inputDevice is system_monitor but sinks list is empty', () => {
    render(
      <ConfigPanel
        {...makeDefaultProps()}
        inputDevice="system_monitor"
        monitorSinks={[]}
      />
    )
    expect(screen.queryByLabelText(/output sink/i)).not.toBeInTheDocument()
  })

  it('calls onInputDeviceChange with system_monitor and selected sink when output sink changes', async () => {
    const user = userEvent.setup()
    const props = {
      ...makeDefaultProps(),
      inputDevice: 'system_monitor' as string | number,
      systemMonitorSink: 'sink1',
      monitorSinks: SINK_OPTIONS,
    }
    render(<ConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/output sink/i))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText('HDMI Audio'))

    expect(props.onInputDeviceChange).toHaveBeenCalledWith('system_monitor', 'sink2')
  })

  // -------------------------------------------------------------------------
  // Fallback device options (empty inputDevices list)
  // -------------------------------------------------------------------------

  it('shows fallback device options when inputDevices prop is empty', async () => {
    const user = userEvent.setup()
    const props = { ...makeDefaultProps(), inputDevices: [] }
    render(<ConfigPanel {...props} />)

    await user.click(screen.getByLabelText(/audio input/i))
    const listbox = await screen.findByRole('listbox')
    expect(within(listbox).getByText('System Default (microphone)')).toBeInTheDocument()
    expect(within(listbox).getByText('System Audio Output (loopback)')).toBeInTheDocument()
  })
})
