import { render as rtlRender, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AccountMenu } from '../AccountMenu'
import type { UserProfile, VoiceOption } from '../../../types/ws'

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
  { id: 'v2', name: 'Voice 2', label: 'Voice Two' },
]

function makeProps(overrides: Partial<Parameters<typeof AccountMenu>[0]> = {}) {
  return {
    profile: mockProfile,
    onUpdateProfile: vi.fn(),
    onChangePassword: vi.fn(),
    onLogout: vi.fn(),
    voices: mockVoices,
    voicePreviewBusy: false,
    onPreviewVoice: vi.fn(),
    stationLengthScale: 1.0,
    onSaveTtsPrefs: vi.fn(),
    showConfig: false,
    onToggleConfig: vi.fn(),
    showAdmin: false,
    onToggleAdmin: vi.fn(),
    ...overrides,
  }
}

describe('AccountMenu', () => {
  describe('trigger button', () => {
    it('renders account menu button with display name', () => {
      render(<AccountMenu {...makeProps()} />)
      expect(screen.getByRole('button', { name: /account menu/i })).toBeInTheDocument()
      expect(screen.getByText('Alice')).toBeInTheDocument()
    })

    it('shows avatar emoji in the button', () => {
      render(<AccountMenu {...makeProps()} />)
      expect(screen.getByText('👤')).toBeInTheDocument()
    })
  })

  describe('menu opens and closes', () => {
    it('opens menu when button clicked', async () => {
      render(<AccountMenu {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => {
        expect(screen.getByText('Edit Profile')).toBeInTheDocument()
        expect(screen.getByText('Change Password')).toBeInTheDocument()
        expect(screen.getByText('Sign Out')).toBeInTheDocument()
      })
    })

    it('shows user display name and callsign in menu header', async () => {
      render(<AccountMenu {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => {
        expect(screen.getAllByText('Alice').length).toBeGreaterThan(0)
        expect(screen.getByText('W1AAA')).toBeInTheDocument()
      })
    })

    it('shows "No call sign set" when callsign is empty', async () => {
      const profile = { ...mockProfile, callsign: '' }
      render(<AccountMenu {...makeProps({ profile })} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => {
        expect(screen.getByText('No call sign set')).toBeInTheDocument()
      })
    })

    it('shows Settings menu item', async () => {
      render(<AccountMenu {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument()
      })
    })

    it('shows Admin Settings menu item for admin users', async () => {
      render(<AccountMenu {...makeProps({ profile: { ...mockProfile, is_admin: true } })} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => {
        expect(screen.getByText('Admin Settings')).toBeInTheDocument()
      })
    })

    it('hides Admin Settings menu item for non-admin users', async () => {
      render(<AccountMenu {...makeProps({ profile: { ...mockProfile, is_admin: false } })} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => {
        expect(screen.queryByText('Admin Settings')).not.toBeInTheDocument()
      })
    })
  })

  describe('callbacks from menu', () => {
    it('calls onLogout when Sign Out clicked', async () => {
      const onLogout = vi.fn()
      render(<AccountMenu {...makeProps({ onLogout })} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => screen.getByText('Sign Out'))
      fireEvent.click(screen.getByText('Sign Out'))
      expect(onLogout).toHaveBeenCalledTimes(1)
    })

    it('calls onToggleConfig when Settings clicked', async () => {
      const onToggleConfig = vi.fn()
      render(<AccountMenu {...makeProps({ onToggleConfig })} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => screen.getByText('Settings'))
      fireEvent.click(screen.getByText('Settings'))
      expect(onToggleConfig).toHaveBeenCalledTimes(1)
    })

    it('calls onToggleAdmin when Admin Settings clicked', async () => {
      const onToggleAdmin = vi.fn()
      render(<AccountMenu {...makeProps({ onToggleAdmin, profile: { ...mockProfile, is_admin: true } })} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => screen.getByText('Admin Settings'))
      fireEvent.click(screen.getByText('Admin Settings'))
      expect(onToggleAdmin).toHaveBeenCalledTimes(1)
    })
  })

  describe('Edit Profile dialog', () => {
    beforeEach(async () => {
      // No setup needed per-test here — each test opens its own
    })

    async function openEditDialog(props = makeProps()) {
      render(<AccountMenu {...props} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => screen.getByText('Edit Profile'))
      fireEvent.click(screen.getByText('Edit Profile'))
      await waitFor(() => screen.getByRole('dialog'))
    }

    it('opens edit profile dialog when Edit Profile clicked', async () => {
      await openEditDialog()
      expect(screen.getByText('Edit Profile')).toBeInTheDocument()
    })

    it('prefills form fields with current profile', async () => {
      await openEditDialog()
      expect(screen.getByDisplayValue('Alice Smith')).toBeInTheDocument()
      expect(screen.getByDisplayValue('W1AAA')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Grand Rapids, MI')).toBeInTheDocument()
    })

    it('shows emoji picker options', async () => {
      await openEditDialog()
      // EMOJI_OPTIONS has 10 emojis — check first two
      expect(screen.getByRole('button', { name: 'Select avatar 👤' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Select avatar 👨' })).toBeInTheDocument()
    })

    it('calls onUpdateProfile and onSaveTtsPrefs when Save clicked', async () => {
      const onUpdateProfile = vi.fn()
      const onSaveTtsPrefs = vi.fn()
      await openEditDialog(makeProps({ onUpdateProfile, onSaveTtsPrefs }))
      fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
      expect(onUpdateProfile).toHaveBeenCalledOnce()
      expect(onSaveTtsPrefs).toHaveBeenCalledOnce()
    })

    it('closes dialog when Cancel clicked', async () => {
      await openEditDialog()
      fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('shows TTS voice section when voices provided', async () => {
      await openEditDialog()
      expect(screen.getByLabelText(/preview selected voice/i)).toBeInTheDocument()
    })

    it('hides TTS voice section when no voices', async () => {
      await openEditDialog(makeProps({ voices: [] }))
      expect(screen.queryByLabelText(/preview selected voice/i)).not.toBeInTheDocument()
    })

    it('voice sample button shows Playing when busy', async () => {
      await openEditDialog(makeProps({ voicePreviewBusy: true }))
      expect(screen.getByText('Playing…')).toBeInTheDocument()
    })

    it('calls onPreviewVoice when Sample button clicked', async () => {
      const onPreviewVoice = vi.fn()
      await openEditDialog(makeProps({ onPreviewVoice }))
      fireEvent.click(screen.getByLabelText(/preview selected voice/i))
      expect(onPreviewVoice).toHaveBeenCalledTimes(1)
    })

    it('shows station default text when customSpeed is false', async () => {
      await openEditDialog()
      expect(screen.getByText(/station default/i)).toBeInTheDocument()
    })

    it('callsign is uppercased on input', async () => {
      const user = userEvent.setup()
      await openEditDialog()
      const callsignField = screen.getByDisplayValue('W1AAA')
      await user.clear(callsignField)
      await user.type(callsignField, 'kd9abc')
      expect(screen.getByDisplayValue('KD9ABC')).toBeInTheDocument()
    })
  })

  describe('Change Password dialog', () => {
    async function openPasswordDialog(props = makeProps()) {
      render(<AccountMenu {...props} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => screen.getByText('Change Password'))
      fireEvent.click(screen.getByText('Change Password'))
      await waitFor(() => screen.getAllByRole('dialog'))
    }

    it('opens change password dialog', async () => {
      await openPasswordDialog()
      // Use exact label text to distinguish the two password fields
      expect(screen.getByLabelText('New Password')).toBeInTheDocument()
      expect(screen.getByLabelText('Confirm New Password')).toBeInTheDocument()
    })

    it('shows error when password too short', async () => {
      const user = userEvent.setup()
      await openPasswordDialog()
      await user.type(screen.getByLabelText('New Password'), 'short')
      await user.type(screen.getByLabelText('Confirm New Password'), 'short')
      fireEvent.click(screen.getByRole('button', { name: /^change$/i }))
      await waitFor(() => {
        expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()
      })
    })

    it('shows error when passwords do not match', async () => {
      const user = userEvent.setup()
      await openPasswordDialog()
      await user.type(screen.getByLabelText('New Password'), 'password123')
      await user.type(screen.getByLabelText('Confirm New Password'), 'different456')
      fireEvent.click(screen.getByRole('button', { name: /^change$/i }))
      await waitFor(() => {
        expect(screen.getByText(/do not match/i)).toBeInTheDocument()
      })
    })

    it('calls onChangePassword when valid passwords submitted', async () => {
      const onChangePassword = vi.fn()
      const user = userEvent.setup()
      await openPasswordDialog(makeProps({ onChangePassword }))
      await user.type(screen.getByLabelText('New Password'), 'validPass99')
      await user.type(screen.getByLabelText('Confirm New Password'), 'validPass99')
      fireEvent.click(screen.getByRole('button', { name: /^change$/i }))
      expect(onChangePassword).toHaveBeenCalledWith('validPass99')
    })

    it('Change button is disabled when fields empty', async () => {
      await openPasswordDialog()
      expect(screen.getByRole('button', { name: /^change$/i })).toBeDisabled()
    })

    it('closes dialog when Cancel clicked', async () => {
      await openPasswordDialog()
      // find the Cancel inside the password dialog (there may be multiple dialogs)
      const cancelBtns = screen.getAllByRole('button', { name: /cancel/i })
      fireEvent.click(cancelBtns[cancelBtns.length - 1])
      await waitFor(() => {
        expect(screen.queryByLabelText(/new password/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('profile sync effect', () => {
    it('does not sync form when edit dialog is open', async () => {
      // Open edit dialog, then verify form is still showing old values
      render(<AccountMenu {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
      await waitFor(() => screen.getByText('Edit Profile'))
      fireEvent.click(screen.getByText('Edit Profile'))
      await waitFor(() => screen.getByRole('dialog'))
      // Fields should still show original values
      expect(screen.getByDisplayValue('Alice Smith')).toBeInTheDocument()
    })
  })
})
