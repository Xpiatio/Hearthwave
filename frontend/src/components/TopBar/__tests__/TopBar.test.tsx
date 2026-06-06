import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TopBar } from '../TopBar'
import type { UserProfile, VoiceOption } from '../../../types/ws'

// VoicePTT uses AudioContext / MediaDevices — mock it at module level
vi.mock('../../VoicePTT/VoicePTT', () => ({
  VoicePTT: () => <button aria-label="Voice PTT (mock)">PTT</button>,
}))

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const mockProfile: UserProfile = {
  id: 'u1',
  display_name: 'Alice',
  avatar_emoji: '👤',
  operator_name: 'Alice Smith',
  callsign: 'W1AAA',
  location: 'Grand Rapids, MI',
  is_admin: true,
  created_at: '2024-01-01T00:00:00Z',
  prefs: {
    dark_mode: false,
    panel_order: [],
    filter_profanity: false,
    listen_only: false,
    read_aloud: false,
    notifications_enabled: false,
    spectro_colormap: 'viridis',
    spectro_time_window_s: 30,
    tts_voice: '',
    tts_length_scale: 0,
  },
}

const mockVoices: VoiceOption[] = [
  { id: 'v1', name: 'Voice 1', label: 'Voice One' },
]

function makeProps(overrides: Partial<Parameters<typeof TopBar>[0]> = {}) {
  return {
    profile: mockProfile,
    stationStatus: 'READY',
    connected: true,
    isOnline: true,
    serviceMode: 'GMRS',
    listenOnly: false,
    readAloud: false,
    onToggleReadAloud: vi.fn(),
    notificationsEnabled: false,
    onToggleNotifications: vi.fn(),
    showAttendance: false,
    onToggleAttendance: vi.fn(),
    showJournal: false,
    onToggleJournal: vi.fn(),
    showContacts: false,
    onToggleContacts: vi.fn(),
    showConfig: false,
    onToggleConfig: vi.fn(),
    showAdmin: false,
    onToggleAdmin: vi.fn(),
    showServerConfig: false,
    onToggleServerConfig: vi.fn(),
    showNcs: false,
    onToggleNcs: vi.fn(),
    showWaterfall: false,
    onToggleWaterfall: vi.fn(),
    darkMode: false,
    onToggleDark: vi.fn(),
    onToggleServiceMode: vi.fn(),
    onToggleListenOnly: vi.fn(),
    sttListening: false,
    onToggleSttListening: vi.fn(),
    onClearChat: vi.fn(),
    onUpdateProfile: vi.fn(),
    onChangePassword: vi.fn(),
    onLogout: vi.fn(),
    voices: mockVoices,
    voicePreviewBusy: false,
    onPreviewVoice: vi.fn(),
    stationLengthScale: 1.0,
    onSaveTtsPrefs: vi.fn(),
    transmitting: false,
    onVoicePttStart: vi.fn(),
    onVoicePttChunk: vi.fn(),
    onVoicePttEnd: vi.fn(),
    onVoicePttCancel: vi.fn(),
    onTxAbort: vi.fn(),
    ...overrides,
  }
}

describe('TopBar', () => {
  describe('renders without crashing', () => {
    it('mounts with default props', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByText('STATION STATUS:')).toBeInTheDocument()
    })
  })

  describe('station status display', () => {
    it('shows stationStatus when connected', () => {
      render(<TopBar {...makeProps({ connected: true, stationStatus: 'READY' })} />)
      expect(screen.getByText('READY')).toBeInTheDocument()
    })

    it('shows OFFLINE when not connected', () => {
      render(<TopBar {...makeProps({ connected: false, stationStatus: 'READY' })} />)
      expect(screen.getByText('OFFLINE')).toBeInTheDocument()
    })

    it('shows FCC online indicator when isOnline is true', () => {
      render(<TopBar {...makeProps({ isOnline: true })} />)
      expect(screen.getByLabelText('FCC lookup online')).toBeInTheDocument()
    })

    it('shows FCC offline indicator when isOnline is false', () => {
      render(<TopBar {...makeProps({ isOnline: false })} />)
      expect(screen.getByLabelText('FCC lookup offline')).toBeInTheDocument()
    })

    it('hides FCC indicator when isOnline is null', () => {
      render(<TopBar {...makeProps({ isOnline: null })} />)
      expect(screen.queryByLabelText(/FCC lookup/)).not.toBeInTheDocument()
    })
  })

  describe('panel toggle buttons', () => {
    it('renders STATIONS toggle', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByRole('button', { name: /toggle stations heard panel/i })).toBeInTheDocument()
    })

    it('renders JOURNAL toggle', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByRole('button', { name: /toggle journal panel/i })).toBeInTheDocument()
    })

    it('renders CONTACTS toggle', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByRole('button', { name: /toggle contacts/i })).toBeInTheDocument()
    })

    it('renders WATERFALL toggle', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByRole('button', { name: /show waterfall/i })).toBeInTheDocument()
    })

    it('calls onToggleAttendance when STATIONS clicked', () => {
      const onToggleAttendance = vi.fn()
      render(<TopBar {...makeProps({ onToggleAttendance })} />)
      fireEvent.click(screen.getByRole('button', { name: /toggle stations heard panel/i }))
      expect(onToggleAttendance).toHaveBeenCalledTimes(1)
    })

    it('calls onToggleJournal when JOURNAL clicked', () => {
      const onToggleJournal = vi.fn()
      render(<TopBar {...makeProps({ onToggleJournal })} />)
      fireEvent.click(screen.getByRole('button', { name: /toggle journal panel/i }))
      expect(onToggleJournal).toHaveBeenCalledTimes(1)
    })

    it('calls onToggleContacts when CONTACTS clicked', () => {
      const onToggleContacts = vi.fn()
      render(<TopBar {...makeProps({ onToggleContacts })} />)
      fireEvent.click(screen.getByRole('button', { name: /toggle contacts/i }))
      expect(onToggleContacts).toHaveBeenCalledTimes(1)
    })

    it('calls onToggleWaterfall when WATERFALL clicked', () => {
      const onToggleWaterfall = vi.fn()
      render(<TopBar {...makeProps({ onToggleWaterfall })} />)
      fireEvent.click(screen.getByRole('button', { name: /show waterfall/i }))
      expect(onToggleWaterfall).toHaveBeenCalledTimes(1)
    })
  })

  describe('NCS MODE button (admin only)', () => {
    it('shows NCS MODE button for admin users', () => {
      const adminProfile = { ...mockProfile, is_admin: true }
      render(<TopBar {...makeProps({ profile: adminProfile })} />)
      expect(screen.getByRole('button', { name: /show ncs panel/i })).toBeInTheDocument()
    })

    it('hides NCS MODE button for non-admin users', () => {
      const nonAdminProfile = { ...mockProfile, is_admin: false }
      render(<TopBar {...makeProps({ profile: nonAdminProfile })} />)
      expect(screen.queryByRole('button', { name: /ncs/i })).not.toBeInTheDocument()
    })

    it('calls onToggleNcs when NCS MODE clicked', () => {
      const onToggleNcs = vi.fn()
      render(<TopBar {...makeProps({ onToggleNcs, profile: { ...mockProfile, is_admin: true } })} />)
      fireEvent.click(screen.getByRole('button', { name: /show ncs panel/i }))
      expect(onToggleNcs).toHaveBeenCalledTimes(1)
    })
  })

  describe('radio operation controls', () => {
    it('displays service mode label', () => {
      render(<TopBar {...makeProps({ serviceMode: 'GMRS' })} />)
      expect(screen.getByRole('button', { name: /service mode: gmrs/i })).toBeInTheDocument()
    })

    it('calls onToggleServiceMode when service mode button clicked', () => {
      const onToggleServiceMode = vi.fn()
      render(<TopBar {...makeProps({ onToggleServiceMode })} />)
      fireEvent.click(screen.getByRole('button', { name: /service mode:/i }))
      expect(onToggleServiceMode).toHaveBeenCalledTimes(1)
    })

    it('shows LISTEN when sttListening is false', () => {
      render(<TopBar {...makeProps({ sttListening: false })} />)
      expect(screen.getByText('LISTEN')).toBeInTheDocument()
    })

    it('shows LISTENING when sttListening is true', () => {
      render(<TopBar {...makeProps({ sttListening: true })} />)
      expect(screen.getByText('LISTENING')).toBeInTheDocument()
    })

    it('calls onToggleSttListening when listen button clicked', () => {
      const onToggleSttListening = vi.fn()
      render(<TopBar {...makeProps({ onToggleSttListening })} />)
      fireEvent.click(screen.getByLabelText(/listening stopped/i))
      expect(onToggleSttListening).toHaveBeenCalledTimes(1)
    })

    it('shows TX ENABLED when listenOnly is false', () => {
      render(<TopBar {...makeProps({ listenOnly: false })} />)
      expect(screen.getByText('TX ENABLED')).toBeInTheDocument()
    })

    it('shows LISTEN ONLY when listenOnly is true', () => {
      render(<TopBar {...makeProps({ listenOnly: true })} />)
      expect(screen.getByText('LISTEN ONLY')).toBeInTheDocument()
    })

    it('calls onToggleListenOnly when TX button clicked', () => {
      const onToggleListenOnly = vi.fn()
      render(<TopBar {...makeProps({ onToggleListenOnly })} />)
      fireEvent.click(screen.getByLabelText(/transmit enabled/i))
      expect(onToggleListenOnly).toHaveBeenCalledTimes(1)
    })

    it('shows READ ALOUD button', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByText('READ ALOUD')).toBeInTheDocument()
    })

    it('calls onToggleReadAloud when READ ALOUD clicked', () => {
      const onToggleReadAloud = vi.fn()
      render(<TopBar {...makeProps({ onToggleReadAloud })} />)
      fireEvent.click(screen.getByText('READ ALOUD'))
      expect(onToggleReadAloud).toHaveBeenCalledTimes(1)
    })

    it('shows NOTIFY button', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByText('NOTIFY')).toBeInTheDocument()
    })

    it('calls onToggleNotifications when NOTIFY clicked', () => {
      const onToggleNotifications = vi.fn()
      render(<TopBar {...makeProps({ onToggleNotifications })} />)
      fireEvent.click(screen.getByText('NOTIFY'))
      expect(onToggleNotifications).toHaveBeenCalledTimes(1)
    })
  })

  describe('ABORT TX button', () => {
    it('renders the ABORT TX button', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByRole('button', { name: /abort transmission/i })).toBeInTheDocument()
    })

    it('is disabled when not transmitting', () => {
      render(<TopBar {...makeProps({ transmitting: false })} />)
      expect(screen.getByRole('button', { name: /abort transmission/i })).toBeDisabled()
    })

    it('is enabled when transmitting', () => {
      render(<TopBar {...makeProps({ transmitting: true })} />)
      expect(screen.getByRole('button', { name: /abort transmission/i })).not.toBeDisabled()
    })

    it('calls onTxAbort when clicked while transmitting', () => {
      const onTxAbort = vi.fn()
      render(<TopBar {...makeProps({ transmitting: true, onTxAbort })} />)
      fireEvent.click(screen.getByRole('button', { name: /abort transmission/i }))
      expect(onTxAbort).toHaveBeenCalledTimes(1)
    })

    it('does not call onTxAbort when clicked while disabled', () => {
      const onTxAbort = vi.fn()
      render(<TopBar {...makeProps({ transmitting: false, onTxAbort })} />)
      // disabled buttons ignore click events
      fireEvent.click(screen.getByRole('button', { name: /abort transmission/i }))
      expect(onTxAbort).not.toHaveBeenCalled()
    })
  })

  describe('utility controls', () => {
    it('renders clear chat button', () => {
      render(<TopBar {...makeProps()} />)
      expect(screen.getByRole('button', { name: /clear chat log/i })).toBeInTheDocument()
    })

    it('calls onClearChat when clear button clicked', () => {
      const onClearChat = vi.fn()
      render(<TopBar {...makeProps({ onClearChat })} />)
      fireEvent.click(screen.getByRole('button', { name: /clear chat log/i }))
      expect(onClearChat).toHaveBeenCalledTimes(1)
    })

    it('renders dark mode toggle', () => {
      render(<TopBar {...makeProps({ darkMode: false })} />)
      expect(screen.getByRole('button', { name: /switch to dark mode/i })).toBeInTheDocument()
    })

    it('renders light mode toggle when dark', () => {
      render(<TopBar {...makeProps({ darkMode: true })} />)
      expect(screen.getByRole('button', { name: /switch to light mode/i })).toBeInTheDocument()
    })

    it('calls onToggleDark when dark mode button clicked', () => {
      const onToggleDark = vi.fn()
      render(<TopBar {...makeProps({ onToggleDark })} />)
      fireEvent.click(screen.getByRole('button', { name: /switch to dark mode/i }))
      expect(onToggleDark).toHaveBeenCalledTimes(1)
    })
  })

  describe('selected/active states', () => {
    it('applies selected state to STATIONS toggle', () => {
      render(<TopBar {...makeProps({ showAttendance: true })} />)
      const btn = screen.getByRole('button', { name: /toggle stations heard panel/i })
      expect(btn).toHaveAttribute('aria-pressed', 'true')
    })

    it('applies selected state to JOURNAL toggle', () => {
      render(<TopBar {...makeProps({ showJournal: true })} />)
      const btn = screen.getByRole('button', { name: /toggle journal panel/i })
      expect(btn).toHaveAttribute('aria-pressed', 'true')
    })
  })
})
