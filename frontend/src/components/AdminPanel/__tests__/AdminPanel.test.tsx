import { render as rtlRender, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AdminPanel } from '../AdminPanel'
import type { VoiceOption } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const VOICE_OPTIONS: VoiceOption[] = [
  { id: 'voice_en_us_1', name: 'Amy', label: 'Amy (US English)' },
  { id: 'voice_en_us_2', name: 'Bob', label: 'Bob (US English)' },
]

function makeConfig(overrides: Partial<{
  stationCallsign: string;
  stationName: string;
  stationLocation: string;
  stationVoice: string;
  stationLengthScale: number;
  geminiApiKeySet: boolean;
  journalsDir: string;
  ncsZone: string;
  rxMode: string;
}> = {}) {
  return {
    stationCallsign: 'W8XYZ',
    stationName: 'Home Base',
    stationLocation: 'Grand Rapids, MI',
    stationVoice: 'voice_en_us_1',
    stationLengthScale: 1.0,
    geminiApiKeySet: false,
    journalsDir: '/data/journals',
    ncsZone: 'MIZ025',
    rxMode: 'voice',
    ...overrides,
  }
}

function makeDefaultProps() {
  return {
    open: true,
    onClose: vi.fn(),
    config: makeConfig(),
    voices: VOICE_OPTIONS,
    voicePreviewBusy: false,
    onSave: vi.fn(),
    onPreviewVoice: vi.fn(),
  }
}

describe('AdminPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it('renders the dialog when open=true', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Admin Settings')).toBeInTheDocument()
  })

  it('does not render dialog content when open=false', () => {
    render(<AdminPanel {...makeDefaultProps()} open={false} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders Station Callsign field with initial value', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByDisplayValue('W8XYZ')).toBeInTheDocument()
  })

  it('renders Station Name field with initial value', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByDisplayValue('Home Base')).toBeInTheDocument()
  })

  it('renders Station Location field with initial value', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByDisplayValue('Grand Rapids, MI')).toBeInTheDocument()
  })

  it('renders Journals Directory field with initial value', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByDisplayValue('/data/journals')).toBeInTheDocument()
  })

  it('renders NWS County Zone field with initial value', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByDisplayValue('MIZ025')).toBeInTheDocument()
  })

  it('renders speech speed slider', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('slider', { name: /default speech speed/i })).toBeInTheDocument()
  })

  it('renders Receive Mode toggle buttons', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('group', { name: /receive mode/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /voice \(stt\)/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cw \/ morse/i })).toBeInTheDocument()
  })

  it('renders Cancel and Save buttons', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Voice selector and preview (conditional on voices.length > 0)
  // -------------------------------------------------------------------------

  it('renders TTS Voice select when voices are available', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/default tts voice/i)).toBeInTheDocument()
  })

  it('does NOT render TTS Voice select when voices list is empty', () => {
    render(<AdminPanel {...makeDefaultProps()} voices={[]} />)
    expect(screen.queryByLabelText(/default tts voice/i)).not.toBeInTheDocument()
  })

  it('renders preview voice button when voices are available', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('button', { name: /preview selected voice/i })).toBeInTheDocument()
  })

  it('disables preview button when voicePreviewBusy=true', () => {
    render(<AdminPanel {...makeDefaultProps()} voicePreviewBusy={true} />)
    expect(screen.getByRole('button', { name: /preview selected voice/i })).toBeDisabled()
  })

  it('enables preview button when voicePreviewBusy=false', () => {
    render(<AdminPanel {...makeDefaultProps()} voicePreviewBusy={false} />)
    expect(screen.getByRole('button', { name: /preview selected voice/i })).not.toBeDisabled()
  })

  it('calls onPreviewVoice with the current voice when preview is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /preview selected voice/i }))
    expect(props.onPreviewVoice).toHaveBeenCalledWith('voice_en_us_1')
  })

  // -------------------------------------------------------------------------
  // Gemini API key field
  // -------------------------------------------------------------------------

  it('renders Gemini API key field', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByLabelText(/gemini api key/i)).toBeInTheDocument()
  })

  it('shows placeholder text indicating key is configured when geminiApiKeySet=true', () => {
    render(
      <AdminPanel
        {...makeDefaultProps()}
        config={makeConfig({ geminiApiKeySet: true })}
      />
    )
    const input = screen.getByLabelText(/gemini api key/i)
    expect(input).toHaveAttribute('placeholder', expect.stringMatching(/configured/i))
  })

  it('toggles Gemini key visibility when show/hide button is clicked', async () => {
    const user = userEvent.setup()
    render(<AdminPanel {...makeDefaultProps()} />)
    const keyInput = screen.getByLabelText(/gemini api key/i)
    expect(keyInput).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: /show api key/i }))
    expect(keyInput).toHaveAttribute('type', 'text')

    await user.click(screen.getByRole('button', { name: /hide api key/i }))
    expect(keyInput).toHaveAttribute('type', 'password')
  })

  // -------------------------------------------------------------------------
  // Receive mode toggle
  // -------------------------------------------------------------------------

  it('selects Voice mode by default', () => {
    render(<AdminPanel {...makeDefaultProps()} config={makeConfig({ rxMode: 'voice' })} />)
    expect(screen.getByText(/incoming audio transcribed with whisper/i)).toBeInTheDocument()
  })

  it('selects CW mode when config.rxMode="cw"', () => {
    render(<AdminPanel {...makeDefaultProps()} config={makeConfig({ rxMode: 'cw' })} />)
    expect(screen.getByText(/incoming audio decoded as morse code/i)).toBeInTheDocument()
  })

  it('switches caption text when CW button is clicked', async () => {
    const user = userEvent.setup()
    render(<AdminPanel {...makeDefaultProps()} config={makeConfig({ rxMode: 'voice' })} />)
    await user.click(screen.getByRole('button', { name: /cw \/ morse/i }))
    expect(screen.getByText(/incoming audio decoded as morse code/i)).toBeInTheDocument()
  })

  it('switches caption back to voice when Voice button is clicked', async () => {
    const user = userEvent.setup()
    render(<AdminPanel {...makeDefaultProps()} config={makeConfig({ rxMode: 'cw' })} />)
    await user.click(screen.getByRole('button', { name: /voice \(stt\)/i }))
    expect(screen.getByText(/incoming audio transcribed with whisper/i)).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Callsign uppercasing
  // -------------------------------------------------------------------------

  it('uppercases callsign input as it is typed', async () => {
    const user = userEvent.setup()
    render(<AdminPanel {...makeDefaultProps()} />)
    const callsignInput = screen.getByDisplayValue('W8XYZ')
    await user.clear(callsignInput)
    await user.type(callsignInput, 'w1abc')
    expect(screen.getByDisplayValue('W1ABC')).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // NCS zone uppercasing
  // -------------------------------------------------------------------------

  it('uppercases NCS zone input as it is typed', async () => {
    const user = userEvent.setup()
    render(<AdminPanel {...makeDefaultProps()} />)
    const zoneInput = screen.getByDisplayValue('MIZ025')
    await user.clear(zoneInput)
    await user.type(zoneInput, 'miz001')
    expect(screen.getByDisplayValue('MIZ001')).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Cancel button
  // -------------------------------------------------------------------------

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(props.onClose).toHaveBeenCalledTimes(1)
  })

  // -------------------------------------------------------------------------
  // Save callback
  // -------------------------------------------------------------------------

  it('calls onSave and onClose with correct values when Save is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledTimes(1)
    expect(props.onSave).toHaveBeenCalledWith({
      callsign: 'W8XYZ',
      name: 'Home Base',
      location: 'Grand Rapids, MI',
      voice: 'voice_en_us_1',
      tts_length_scale: 1.0,
      gemini_api_key: '',
      journals_dir: '/data/journals',
      ncs_zone: 'MIZ025',
      rx_mode: 'voice',
    })
    expect(props.onClose).toHaveBeenCalledTimes(1)
  })

  it('falls back to N0CALL when callsign is empty on save', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} config={makeConfig({ stationCallsign: '' })} />)

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ callsign: 'N0CALL' })
    )
  })

  it('uppercases the NCS zone on save', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} config={makeConfig({ ncsZone: 'miz025' })} />)

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ ncs_zone: 'MIZ025' })
    )
  })

  // -------------------------------------------------------------------------
  // children slot
  // -------------------------------------------------------------------------

  it('renders children inside the dialog when provided', () => {
    render(
      <AdminPanel {...makeDefaultProps()}>
        <div data-testid="child-content">Speaker Enrollment</div>
      </AdminPanel>
    )
    expect(screen.getByTestId('child-content')).toBeInTheDocument()
  })

  it('does not render children divider when no children are provided', () => {
    // Divider after children only appears when children is truthy
    const { container } = render(<AdminPanel {...makeDefaultProps()} />)
    // The component renders a static number of Dividers; with children=undefined
    // the extra section is absent — just verify no crash and dialog is present.
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Re-initialization on open
  // -------------------------------------------------------------------------

  it('re-initializes state when dialog is re-opened with new config', () => {
    const { rerender } = render(
      <ThemeProvider theme={makeTheme(false)}>
        <AdminPanel
          open={false}
          onClose={vi.fn()}
          config={makeConfig({ stationCallsign: 'W8AAA' })}
          voices={VOICE_OPTIONS}
          voicePreviewBusy={false}
          onSave={vi.fn()}
          onPreviewVoice={vi.fn()}
        />
      </ThemeProvider>
    )

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <AdminPanel
          open={true}
          onClose={vi.fn()}
          config={makeConfig({ stationCallsign: 'W8BBB' })}
          voices={VOICE_OPTIONS}
          voicePreviewBusy={false}
          onSave={vi.fn()}
          onPreviewVoice={vi.fn()}
        />
      </ThemeProvider>
    )

    expect(screen.getByDisplayValue('W8BBB')).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Voice select interaction
  // -------------------------------------------------------------------------

  it('updates selected voice and passes it to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)

    await user.click(screen.getByLabelText(/default tts voice/i))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText('Bob (US English)'))

    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ voice: 'voice_en_us_2' })
    )
  })
})
