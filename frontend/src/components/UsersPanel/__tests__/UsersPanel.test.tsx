import { render as rtlRender, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { UsersPanel } from '../UsersPanel'
import type { UserProfile } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

function makeProfile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: 'user-1',
    display_name: 'Alice',
    avatar_emoji: '👤',
    operator_name: 'Alice Smith',
    callsign: 'W1AAA',
    location: 'Grand Rapids, MI',
    is_admin: false,
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
    },
    ...overrides,
  }
}

const ADMIN_PROFILE = makeProfile({
  id: 'admin-1',
  display_name: 'Admin',
  operator_name: 'Admin',
  callsign: 'W8ADM',
  is_admin: true,
})

const USER_PROFILE = makeProfile({
  id: 'user-2',
  display_name: 'Bob',
  operator_name: 'Bob Jones',
  callsign: 'W2BOB',
  is_admin: false,
})

function makeDefaultProps() {
  return {
    profiles: [ADMIN_PROFILE, USER_PROFILE],
    currentUserId: 'admin-1',
    onCreateProfile: vi.fn(),
    onDeleteProfile: vi.fn(),
    onResetLockout: vi.fn(),
  }
}

describe('UsersPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it('renders without crashing', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    expect(screen.getByText('User Accounts')).toBeInTheDocument()
  })

  it('renders the New User button', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('button', { name: /new user/i })).toBeInTheDocument()
  })

  it('renders table headers', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    expect(screen.getByText('User')).toBeInTheDocument()
    expect(screen.getByText('Call Sign')).toBeInTheDocument()
    expect(screen.getByText('Role')).toBeInTheDocument()
    expect(screen.getByText('Actions')).toBeInTheDocument()
  })

  it('renders all profiles in the table', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    // ADMIN_PROFILE has display_name="Admin" and is_admin=true, so "Admin" appears
    // both as a body2 text node and as the Chip label — use getAllByText.
    expect(screen.getAllByText('Admin').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Bob')).toBeInTheDocument()
  })

  it('renders callsigns for each profile', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    expect(screen.getByText('W8ADM')).toBeInTheDocument()
    expect(screen.getByText('W2BOB')).toBeInTheDocument()
  })

  it('renders Admin chip for admin profiles', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    // ADMIN_PROFILE has is_admin=true, so a Chip with label "Admin" is rendered.
    // The display_name is also "Admin", so "Admin" appears in at least two nodes.
    const adminTexts = screen.getAllByText('Admin')
    expect(adminTexts.length).toBeGreaterThanOrEqual(2)
    // Verify a MUI Chip span carries the "Admin" label
    const chipLabel = adminTexts.find(
      (el) => el.tagName === 'SPAN' && el.className.includes('Chip')
    )
    expect(chipLabel).toBeTruthy()
  })

  it('renders em-dash for profiles without a callsign', () => {
    const props = {
      ...makeDefaultProps(),
      profiles: [makeProfile({ id: 'user-3', display_name: 'Charlie', callsign: '', is_admin: false })],
    }
    render(<UsersPanel {...props} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('shows operator_name when it differs from display_name', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    // Bob's operator_name is "Bob Jones", display_name is "Bob"
    expect(screen.getByText('Bob Jones')).toBeInTheDocument()
  })

  it('does NOT show operator_name when it equals display_name', () => {
    // Use a profile where display_name !== operator_name for the "shown" case,
    // but this test uses a profile where they are equal — no caption should appear.
    const sameNameProfile = makeProfile({
      id: 'user-x',
      display_name: 'Zara',
      operator_name: 'Zara', // same as display_name
      is_admin: false,
    })
    const props = { ...makeDefaultProps(), profiles: [sameNameProfile] }
    render(<UsersPanel {...props} />)
    // display_name "Zara" should appear (as body2 text)
    expect(screen.getByText('Zara')).toBeInTheDocument()
    // The caption variant carrying operator_name should NOT be present since they match
    // The component only renders operator_name in a <Typography variant="caption"> when they differ
    const allZara = screen.queryAllByText('Zara')
    // Should appear exactly once — only as display_name, not repeated as operator_name
    expect(allZara).toHaveLength(1)
  })

  // -------------------------------------------------------------------------
  // Reset lockout action
  // -------------------------------------------------------------------------

  it('calls onResetLockout with the correct userId when reset lockout button is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)

    const resetButtons = screen.getAllByRole('button', { name: /reset lockout/i })
    // First reset button corresponds to ADMIN_PROFILE
    await user.click(resetButtons[0])
    expect(props.onResetLockout).toHaveBeenCalledWith('admin-1')
  })

  it('calls onResetLockout for other users too', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)

    const resetButtons = screen.getAllByRole('button', { name: /reset lockout/i })
    await user.click(resetButtons[1])
    expect(props.onResetLockout).toHaveBeenCalledWith('user-2')
  })

  // -------------------------------------------------------------------------
  // Delete action
  // -------------------------------------------------------------------------

  it('does NOT show delete button for currentUserId', () => {
    // currentUserId = admin-1; admin row should have no delete button
    render(<UsersPanel {...makeDefaultProps()} />)
    const deleteButtons = screen.getAllByRole('button', { name: /delete user/i })
    // Only USER_PROFILE (user-2) should have a delete button
    expect(deleteButtons).toHaveLength(1)
  })

  it('shows delete button for users other than currentUserId', () => {
    render(<UsersPanel {...makeDefaultProps()} />)
    expect(screen.getByRole('button', { name: /delete user/i })).toBeInTheDocument()
  })

  it('calls onDeleteProfile with correct userId when delete is clicked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)

    await user.click(screen.getByRole('button', { name: /delete user/i }))
    expect(props.onDeleteProfile).toHaveBeenCalledWith('user-2')
  })

  it('shows delete button for all users when currentUserId does not match any', () => {
    const props = { ...makeDefaultProps(), currentUserId: 'nobody' }
    render(<UsersPanel {...props} />)
    const deleteButtons = screen.getAllByRole('button', { name: /delete user/i })
    expect(deleteButtons).toHaveLength(2)
  })

  // -------------------------------------------------------------------------
  // New user dialog — open / close
  // -------------------------------------------------------------------------

  it('opens the create user dialog when New User is clicked', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('New User Account')).toBeInTheDocument()
  })

  it('closes the dialog when Cancel is clicked', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))
    expect(screen.getByText('New User Account')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    // MUI Dialog stays in DOM during exit animation; wait for "New User Account" title to vanish
    await waitFor(() =>
      expect(screen.queryByText('New User Account')).not.toBeInTheDocument()
    )
  })

  // -------------------------------------------------------------------------
  // New user dialog — form fields
  // -------------------------------------------------------------------------

  it('renders all form fields in the create dialog', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/operator name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/call sign/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument()
    // Password fields
    expect(screen.getByLabelText(/^password \*/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    // Admin checkbox
    expect(screen.getByLabelText(/admin/i)).toBeInTheDocument()
  })

  it('renders emoji avatar picker in the create dialog', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))
    expect(screen.getByText('Avatar')).toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // New user dialog — validation errors
  // -------------------------------------------------------------------------

  it('shows error when Create is clicked with empty display name', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))
    await user.click(screen.getByRole('button', { name: /^create$/i }))
    expect(screen.getByText(/display name is required/i)).toBeInTheDocument()
  })

  it('shows error when password is shorter than 8 characters', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Charlie')
    await user.type(screen.getByLabelText(/^password \*/i), 'short')
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument()
  })

  it('shows error when passwords do not match', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Charlie')
    await user.type(screen.getByLabelText(/^password \*/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'different123')
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
  }, 15000)

  // -------------------------------------------------------------------------
  // New user dialog — successful create
  // -------------------------------------------------------------------------

  it('calls onCreateProfile with correct values on valid submission', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Charlie')
    await user.type(screen.getByLabelText(/operator name/i), 'Charlie Brown')
    await user.type(screen.getByLabelText(/call sign/i), 'w3ccc')
    await user.type(screen.getByLabelText(/location/i), 'Detroit, MI')
    await user.type(screen.getByLabelText(/^password \*/i), 'securepass')
    await user.type(screen.getByLabelText(/confirm password/i), 'securepass')

    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(props.onCreateProfile).toHaveBeenCalledTimes(1)
    expect(props.onCreateProfile).toHaveBeenCalledWith({
      display_name: 'Charlie',
      password: 'securepass',
      avatar_emoji: '👤',
      operator_name: 'Charlie Brown',
      callsign: 'W3CCC', // uppercased
      location: 'Detroit, MI',
      is_admin: false,
    })
  }, 20000)

  it('closes the dialog after successful create', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Dave')
    await user.type(screen.getByLabelText(/^password \*/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    // MUI Dialog stays in DOM during exit animation; wait for title to vanish
    await waitFor(() =>
      expect(screen.queryByText('New User Account')).not.toBeInTheDocument()
    )
  }, 15000)

  it('defaults operator_name to display_name when operator name is left empty', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Eve')
    await user.type(screen.getByLabelText(/^password \*/i), 'evepass1')
    await user.type(screen.getByLabelText(/confirm password/i), 'evepass1')
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(props.onCreateProfile).toHaveBeenCalledWith(
      expect.objectContaining({ operator_name: 'Eve' })
    )
  }, 15000)

  it('creates an admin user when the Admin checkbox is checked', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Frank')
    await user.type(screen.getByLabelText(/^password \*/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByLabelText(/admin/i))
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(props.onCreateProfile).toHaveBeenCalledWith(
      expect.objectContaining({ is_admin: true })
    )
  }, 15000)

  // -------------------------------------------------------------------------
  // Avatar emoji selection
  // -------------------------------------------------------------------------

  it('changes the selected avatar emoji', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps()
    render(<UsersPanel {...props} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    // Click the 👨 emoji button (second in list)
    const emojiButtons = within(screen.getByRole('dialog')).getAllByRole('button')
    // Emoji buttons appear before the form action buttons; find by text content
    const manEmoji = emojiButtons.find((btn) => btn.textContent === '👨')
    expect(manEmoji).toBeTruthy()
    await user.click(manEmoji!)

    // Now fill form and submit
    await user.type(screen.getByLabelText(/display name/i), 'Grace')
    await user.type(screen.getByLabelText(/^password \*/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(props.onCreateProfile).toHaveBeenCalledWith(
      expect.objectContaining({ avatar_emoji: '👨' })
    )
  }, 15000)

  // -------------------------------------------------------------------------
  // Error cleared on input change
  // -------------------------------------------------------------------------

  it('clears form error when display name field is updated', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    // Trigger the error
    await user.click(screen.getByRole('button', { name: /^create$/i }))
    expect(screen.getByText(/display name is required/i)).toBeInTheDocument()

    // Type in the field — error should clear
    await user.type(screen.getByLabelText(/display name/i), 'H')
    expect(screen.queryByText(/display name is required/i)).not.toBeInTheDocument()
  })

  it('clears form error when password field is updated', async () => {
    const user = userEvent.setup()
    render(<UsersPanel {...makeDefaultProps()} />)
    await user.click(screen.getByRole('button', { name: /new user/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Hank')
    await user.type(screen.getByLabelText(/^password \*/i), 'bad')
    await user.click(screen.getByRole('button', { name: /^create$/i }))
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()

    await user.type(screen.getByLabelText(/^password \*/i), 'extra')
    expect(screen.queryByText(/at least 8 characters/i)).not.toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Empty profiles list
  // -------------------------------------------------------------------------

  it('renders an empty table body when profiles list is empty', () => {
    render(<UsersPanel {...makeDefaultProps()} profiles={[]} />)
    // Table should still render but have no data rows (only header row)
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(1) // header only
  })
})
