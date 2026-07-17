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
    },
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
