import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { MobileApp } from '../MobileApp'
import type { MobileAppProps } from '../MobileApp'
import type { UserProfile } from '../../../types/ws'

// AudioContext is not available in jsdom; VoicePTT (used by MobileTopBar)
// touches it on mount.
const mockAudioContext = {
  createBuffer: vi.fn(() => ({ getChannelData: vi.fn(() => new Float32Array(10)) })),
  createBufferSource: vi.fn(() => ({
    buffer: null,
    connect: vi.fn(),
    start: vi.fn(),
    onended: null as unknown,
  })),
  destination: {},
  close: vi.fn(),
}
vi.stubGlobal('AudioContext', vi.fn(() => mockAudioContext))

// jsdom doesn't implement scrollIntoView — ChatDisplay calls it on mount.
window.HTMLElement.prototype.scrollIntoView = vi.fn()

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const profile: UserProfile = {
  id: 'u1',
  display_name: 'Ben',
  avatar_emoji: '🙂',
  operator_name: 'Ben',
  callsign: 'WRXB123',
  location: 'Test City',
  is_admin: true,
  role: 'admin',
  created_at: '2026-01-01T00:00:00Z',
  prefs: {
    dark_mode: false,
    filter_profanity: true,
    listen_only: false,
    read_aloud: false,
    notifications_enabled: false,
    spectro_colormap: 'viridis',
    spectro_time_window_s: 30,
  },
}

function makeProps(overrides: Partial<MobileAppProps> = {}): MobileAppProps {
  return {
    profile,
    effectiveCallsign: 'WRXB123',
    connected: true,
    isOnline: true,
    showCallsignChips: true,
    uiLevel: 'simple',
    isKid: false,
    quickMessages: ["I'm OK", 'On my way', 'Call me'],
    familyPresence: [],
    familyReminders: {},
    sendImOk: vi.fn(),
    sendSetReminder: vi.fn(),
    messages: [],
    contacts: [],
    radioStatus: null,
    transmitting: false,
    lastMessage: null,
    channelClear: true,
    attendanceStations: [
      { callsign: 'W1AW', name: 'Test Station', location: 'Test City', gmrs: '', ham: '' },
    ],
    onClearAttendance: vi.fn(),
    journals: [],
    journalResult: null,
    journalGenerating: false,
    journalError: null,
    rxTexts: [],
    rxCallsigns: [],
    onListJournals: vi.fn(),
    onGenerate: vi.fn(),
    onSaveJournal: vi.fn(),
    onDeleteJournal: vi.fn(),
    onPublishJournal: vi.fn(),
    onUnpublishJournal: vi.fn(),
    onDismissJournalResult: vi.fn(),
    listenOnly: true,
    onSend: vi.fn(),
    onChat: vi.fn(),
    onStandaloneId: vi.fn(),
    txComposition: null,
    onVoicePttStart: vi.fn(),
    onVoicePttChunk: vi.fn(),
    onVoicePttEnd: vi.fn(),
    onVoicePttCancel: vi.fn(),
    onTxAbort: vi.fn(),
    sttListening: false,
    serviceMode: 'GMRS',
    readAloud: false,
    notificationsEnabled: false,
    darkMode: false,
    voices: [],
    voicePreviewBusy: false,
    onToggleSttListening: vi.fn(),
    onToggleServiceMode: vi.fn(),
    onToggleReadAloud: vi.fn(),
    onToggleNotifications: vi.fn(),
    onToggleListenOnly: vi.fn(),
    onToggleDark: vi.fn(),
    onUpdateProfile: vi.fn(),
    onChangePassword: vi.fn(),
    onLogout: vi.fn(),
    onPreviewVoice: vi.fn(),
    onSaveTtsPrefs: vi.fn(),
    adminConfig: {
      stationCallsign: 'N0CALL',
      stationName: '',
      stationLocation: '',
      stationVoice: '',
      stationLengthScale: 1.0,
      geminiApiKeySet: false,
      journalsDir: '/data/journals',
      ncsZone: '',
      ncsPreambleText: '',
      ncsClosingText: '',
      rxMode: 'voice',
      netDay: '',
      netTime: '',
    },
    isCoordinator: false,
    neighborhoodState: null,
    incidents: [],
    neighborhoodAlerts: [],
    incidentError: null,
    sendNeighborhoodCheckin: vi.fn(),
    sendIncidentReport: vi.fn(),
    sendStreetAlert: vi.fn(),
    sendNeighborhoodStart: vi.fn(),
    sendNeighborhoodEnd: vi.fn(),
    sendNeighborhoodCallNext: vi.fn(),
    sendNeighborhoodCallReset: vi.fn(),
    showSettings: false,
    onToggleSettings: vi.fn(),
    showContacts: false,
    pendingPrefilledCallsign: undefined,
    pendingPrefilledName: undefined,
    pendingPrefilledLocation: undefined,
    fccLookupResult: null,
    verifyAllComplete: false,
    onContactsClose: vi.fn(),
    onVerifyAllDismiss: vi.fn(),
    send: vi.fn(),
    pendingStations: [],
    onAddPending: vi.fn(),
    onDismissPending: vi.fn(),
    onDismissAllPending: vi.fn(),
    publishSnack: null,
    errorSnack: null,
    journalSavedSnack: null,
    vocabSnack: null,
    onClosePublishSnack: vi.fn(),
    onCloseErrorSnack: vi.fn(),
    onCloseJournalSavedSnack: vi.fn(),
    onCloseVocabSnack: vi.fn(),
    ...overrides,
  }
}

describe('MobileApp — simple tier hides operator-only tabs/panels', () => {
  it('does not render the Stations/Journal bottom-nav tabs or their panels in simple tier', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'simple' })} />)

    expect(screen.queryByRole('button', { name: 'Stations' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Journal' })).not.toBeInTheDocument()
    expect(screen.queryByRole('table', { name: 'Stations heard this session' })).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Journal entries' })).not.toBeInTheDocument()

    // Chat is still available in simple tier.
    expect(screen.getByRole('button', { name: 'Chat' })).toBeInTheDocument()
    // Family and Neighborhood are ungated in both tiers.
    expect(screen.getByRole('button', { name: 'Family' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Neighborhood' })).toBeInTheDocument()
  })

  it('renders the Stations/Journal tabs in operator tier', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)

    expect(screen.getByRole('button', { name: 'Stations' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Journal' })).toBeInTheDocument()
  })

  it('falls back to the Chat tab when the tier flips to simple while parked on an operator-only tab', () => {
    const { rerender } = render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Stations' }))
    expect(screen.getByRole('table', { name: 'Stations heard this session' })).toBeInTheDocument()

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <MobileApp {...makeProps({ uiLevel: 'simple' })} />
      </ThemeProvider>
    )

    expect(screen.queryByRole('table', { name: 'Stations heard this session' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Chat' })).toBeInTheDocument()
  })
})

describe('MobileApp — Family tab', () => {
  it('shows the Family bottom-nav tab in simple tier', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'simple' })} />)
    expect(screen.getByRole('button', { name: 'Family' })).toBeInTheDocument()
  })

  it('shows the Family bottom-nav tab in operator tier', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)
    expect(screen.getByRole('button', { name: 'Family' })).toBeInTheDocument()
  })

  it('renders the FamilyPanel when the Family tab is tapped', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'simple' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Family' }))

    expect(screen.getByRole('list', { name: 'Family members' })).toBeInTheDocument()
  })

  it('unmounts the FamilyPanel when switching away to another tab', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Family' }))
    expect(screen.getByRole('list', { name: 'Family members' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Chat' }))
    expect(screen.queryByRole('list', { name: 'Family members' })).not.toBeInTheDocument()
  })
})

describe('MobileApp — Neighborhood tab', () => {
  it('shows the Neighborhood bottom-nav tab in simple tier', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'simple' })} />)
    expect(screen.getByRole('button', { name: 'Neighborhood' })).toBeInTheDocument()
  })

  it('shows the Neighborhood bottom-nav tab in operator tier', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)
    expect(screen.getByRole('button', { name: 'Neighborhood' })).toBeInTheDocument()
  })

  it('renders the NeighborhoodPanel when the Neighborhood tab is tapped', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'simple' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Neighborhood' }))

    expect(screen.getByRole('heading', { name: 'Neighborhood' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check in' })).toBeInTheDocument()
  })

  it('unmounts the NeighborhoodPanel when switching away to another tab', () => {
    render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Neighborhood' }))
    expect(screen.getByRole('heading', { name: 'Neighborhood' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Chat' }))
    expect(screen.queryByRole('heading', { name: 'Neighborhood' })).not.toBeInTheDocument()
  })

  it('survives the operator-tier clamp like Family when parked on Neighborhood and the tier flips to simple', () => {
    const { rerender } = render(<MobileApp {...makeProps({ uiLevel: 'operator' })} />)

    fireEvent.click(screen.getByRole('button', { name: 'Neighborhood' }))
    expect(screen.getByRole('heading', { name: 'Neighborhood' })).toBeInTheDocument()

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <MobileApp {...makeProps({ uiLevel: 'simple' })} />
      </ThemeProvider>
    )
    expect(screen.getByRole('heading', { name: 'Neighborhood' })).toBeInTheDocument()
  })
})
