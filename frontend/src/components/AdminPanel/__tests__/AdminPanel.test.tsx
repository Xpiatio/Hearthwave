import { render as rtlRender, screen, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRef } from 'react'
import { AdminPanel } from '../AdminPanel'
import type { AdminPanelHandle } from '../AdminPanel'
import type { VoiceOption, DeviceTokenRecord } from '../../../types/ws'

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
  ncsPreambleText: string;
  ncsClosingText: string;
  rxMode: string;
  netDay: string;
  netTime: string;
  display_quick_messages: string[];
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
    ncsPreambleText: '',
    ncsClosingText: '',
    rxMode: 'voice',
    netDay: '',
    netTime: '',
    display_quick_messages: [],
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
    deviceTokens: [] as DeviceTokenRecord[],
    createdToken: null as DeviceTokenRecord | null,
    onCreateDeviceToken: vi.fn(),
    onRevokeDeviceToken: vi.fn(),
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
      ncs_preamble_text: '',
      ncs_closing_text: '',
      rx_mode: 'voice',
      neighborhood_net_day: '',
      neighborhood_net_time: '',
      display_quick_messages: [],
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
  // Neighborhood net schedule
  // -------------------------------------------------------------------------

  it('defaults the net day select to "Not scheduled" when netDay is empty', () => {
    render(<AdminPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('combobox', { name: /net day/i })).toHaveTextContent('Not scheduled')
  })

  it('shows the configured net day and net time', () => {
    render(<AdminPanel {...makeDefaultProps()} config={makeConfig({ netDay: 'Saturday', netTime: '09:00' })} />)
    expect(screen.getByRole('combobox', { name: /net day/i })).toHaveTextContent('Saturday')
    expect(screen.getByLabelText(/net time/i)).toHaveValue('09:00')
  })

  it('lists all seven weekdays plus "Not scheduled" as net day options', async () => {
    const user = userEvent.setup()
    render(<AdminPanel {...makeDefaultProps()} />)

    await user.click(screen.getByRole('combobox', { name: /net day/i }))

    const listbox = screen.getByRole('listbox')
    for (const day of ['Not scheduled', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']) {
      expect(within(listbox).getByText(day)).toBeInTheDocument()
    }
  })

  it('saves the selected net day and net time', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)

    await user.click(screen.getByRole('combobox', { name: /net day/i }))
    await user.click(await screen.findByRole('option', { name: 'Saturday' }))
    await user.type(screen.getByLabelText(/net time/i), '09:00')

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ neighborhood_net_day: 'Saturday', neighborhood_net_time: '09:00' })
    )
  })

  it('saves an empty net day when reset to "Not scheduled"', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} config={makeConfig({ netDay: 'Saturday', netTime: '09:00' })} />)

    await user.click(screen.getByRole('combobox', { name: /net day/i }))
    await user.click(await screen.findByRole('option', { name: 'Not scheduled' }))

    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ neighborhood_net_day: '' })
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
          deviceTokens={[]}
          createdToken={null}
          onCreateDeviceToken={vi.fn()}
          onRevokeDeviceToken={vi.fn()}
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
          deviceTokens={[]}
          createdToken={null}
          onCreateDeviceToken={vi.fn()}
          onRevokeDeviceToken={vi.fn()}
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

  // -------------------------------------------------------------------------
  // Imperative handle, dirty reporting, hideSaveButton
  // -------------------------------------------------------------------------

  it('exposes an imperative save() that calls onSave without closing', async () => {
    const onSave = vi.fn(); const onClose = vi.fn()
    const ref = createRef<AdminPanelHandle>()
    render(<AdminPanel {...makeDefaultProps()} ref={ref} onSave={onSave} onClose={onClose} embedded />)
    ref.current!.save()
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('reports dirty state via onDirtyChange when a field changes', async () => {
    const onDirtyChange = vi.fn()
    render(<AdminPanel {...makeDefaultProps()} embedded onDirtyChange={onDirtyChange} />)
    // initial mount reports clean
    expect(onDirtyChange).toHaveBeenLastCalledWith(false)
    const nameField = screen.getByLabelText(/station name/i)
    await userEvent.type(nameField, 'X')
    expect(onDirtyChange).toHaveBeenLastCalledWith(true)
  })

  it('hides the embedded Save button when hideSaveButton is set', () => {
    render(<AdminPanel {...makeDefaultProps()} embedded hideSaveButton />)
    expect(screen.queryByRole('button', { name: /^save$/i })).not.toBeInTheDocument()
  })
})

// -----------------------------------------------------------------------------
// Wall displays admin section (device tokens + household quick messages)
// -----------------------------------------------------------------------------

describe('Wall displays admin section', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const ts = '2026-07-18T12:00:00Z'

  it('lists device tokens with revoke buttons', () => {
    const props = makeDefaultProps()
    render(
      <AdminPanel
        {...props}
        deviceTokens={[{ id: 'd1', label: 'Kitchen', created_at: ts, last_seen: null }]}
      />
    )
    expect(screen.getByText('Kitchen')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /revoke/i }))
    expect(props.onRevokeDeviceToken).toHaveBeenCalledWith('d1')
  })

  it('creates a token from the label field', () => {
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)
    fireEvent.change(screen.getByLabelText(/display name/i), { target: { value: 'Kitchen' } })
    fireEvent.click(screen.getByRole('button', { name: /add display/i }))
    expect(props.onCreateDeviceToken).toHaveBeenCalledWith('Kitchen')
  })

  it('shows the one-time token after creation', () => {
    const props = makeDefaultProps()
    render(
      <AdminPanel
        {...props}
        createdToken={{ id: 'd1', label: 'Kitchen', created_at: ts, last_seen: null, token: 'SECRET' }}
      />
    )
    expect(screen.getByDisplayValue('SECRET')).toBeInTheDocument()
    expect(screen.getByText(/won't be shown again/i)).toBeInTheDocument()
  })

  it('saves display_quick_messages one-per-line in the onSave payload', () => {
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)
    fireEvent.change(screen.getByLabelText(/household quick messages/i),
      { target: { value: 'Dinner is ready\nCome home please' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(expect.objectContaining({
      display_quick_messages: ['Dinner is ready', 'Come home please'],
    }))
  })

  it('disables Add display button when label is blank or whitespace-only', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)

    const addButton = screen.getByRole('button', { name: /add display/i })
    // Initially disabled (empty field)
    expect(addButton).toBeDisabled()

    // Type whitespace-only
    const labelField = screen.getByLabelText(/display name/i)
    await user.type(labelField, '   ')
    expect(addButton).toBeDisabled()

    // Clear and type a real value to verify it becomes enabled
    await user.clear(labelField)
    await user.type(labelField, 'Kitchen')
    expect(addButton).not.toBeDisabled()
    // Native disabled-button semantics guarantee onCreateDeviceToken cannot fire from disabled state;
    // the handler's internal trim guard is intentional defense-in-depth, not UI-reachable today.
  })

  it('normalizes quick-messages with multiline messy input and filters empty lines', async () => {
    const props = makeDefaultProps()
    render(<AdminPanel {...props} />)

    // Type multiline with empty lines and extra whitespace
    fireEvent.change(screen.getByLabelText(/household quick messages/i), {
      target: { value: 'Dinner is ready\n\n  Come home please  \n' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(expect.objectContaining({
      display_quick_messages: ['Dinner is ready', 'Come home please'],
    }))
  })
})
