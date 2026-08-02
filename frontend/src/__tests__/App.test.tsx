import { render as rtlRender, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '../App'

// App.tsx reads deviceClass from window.matchMedia (useDeviceClass) to pick
// Desktop vs Mobile. jsdom has no matchMedia implementation at all, so it
// must be stubbed before render — installMatchMedia(() => false) means
// neither the phone nor tablet query matches, landing on the "desktop"
// branch, which renders NeighborhoodPanel directly (no bottom-nav tap
// needed) for the coordinator radio-checkin path under test here.
function installMatchMedia(matchFor: (q: string) => boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: matchFor(query),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: () => true,
  })) as unknown as typeof window.matchMedia
}

// useWebSocket opens a real WebSocket and isn't relevant to what's under
// test (the WS *frame shape* App.tsx's senders build) — mocked out so
// `send` calls can be captured directly, and `onMessage` captured so a
// test can simulate an inbound neighborhood_state to populate the roster.
const wsMock = vi.hoisted(() => ({
  send: vi.fn(),
  onMessage: null as ((msg: unknown) => void) | null,
}))

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: (opts: { onMessage: (msg: unknown) => void }) => {
    wsMock.onMessage = opts.onMessage
    return { send: wsMock.send, connected: true }
  },
}))

// useAuth's fetch-driven setup/login flow is irrelevant here — mocked so
// the app renders straight past LoginScreen with a coordinator profile
// (prefs.neighborhood_coordinator: true is what actually gates the
// coordinator-only radio check-in form and station controls).
vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    token: 'test-token',
    profile: {
      id: 'coordinator-1',
      display_name: 'Coordinator Cate',
      avatar_emoji: '🧭',
      operator_name: 'Cate',
      callsign: 'W1AW',
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
        neighborhood_coordinator: true,
      },
    },
    setProfile: vi.fn(),
    loading: false,
    setupNeeded: false,
    setup: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

async function openNeighborhood() {
  const user = userEvent.setup()
  rtlRender(<App />)
  await user.click(screen.getByRole('button', { name: 'Neighborhood' }))
  return user
}

describe('App — coordinator radio check-in WS frame', () => {
  beforeEach(() => {
    installMatchMedia(() => false)
    wsMock.send.mockClear()
    wsMock.onMessage = null
  })

  it('sends save_contact only when the "Save to contacts" checkbox is checked', async () => {
    const user = await openNeighborhood()

    await user.type(screen.getByLabelText('Callsign'), 'WRAZ999')
    await user.type(screen.getByLabelText('Name'), 'Sam')
    await user.click(screen.getByRole('checkbox', { name: 'Save to contacts' }))
    await user.click(screen.getByRole('button', { name: 'Check in station' }))

    expect(wsMock.send).toHaveBeenCalledWith({
      type: 'neighborhood_checkin_radio',
      callsign: 'WRAZ999',
      name: 'Sam',
      location: '',
      save_contact: true,
    })
  })

  it('omits save_contact entirely (not save_contact: false) when the checkbox is left unchecked', async () => {
    const user = await openNeighborhood()

    await user.type(screen.getByLabelText('Callsign'), 'WRAZ998')
    await user.type(screen.getByLabelText('Name'), 'Alex')
    await user.click(screen.getByRole('button', { name: 'Check in station' }))

    // Asserting the whole frame (not just presence/absence of one key) so a
    // dropped field or a save_contact: false regression fails this test.
    expect(wsMock.send).toHaveBeenCalledWith({
      type: 'neighborhood_checkin_radio',
      callsign: 'WRAZ998',
      name: 'Alex',
      location: '',
    })
  })

  it('sends the exact neighborhood_remove_station frame for a radio-checked-in station', async () => {
    const user = await openNeighborhood()

    act(() => {
      wsMock.onMessage?.({
        type: 'neighborhood_state',
        roster: [
          {
            user_id: 'radio-1',
            callsign: 'W9ZZZ',
            name: 'Radio Neighbor',
            location: 'Elm St',
            status: 'checked_in',
            checkin_time: '2026-01-01T00:00:00Z',
            called: false,
            via: 'radio',
          },
        ],
        current_call: null,
        net_day: '',
        net_time: '',
      })
    })

    await user.click(screen.getByRole('button', { name: 'Remove Radio Neighbor' }))

    expect(wsMock.send).toHaveBeenCalledWith({
      type: 'neighborhood_remove_station',
      user_id: 'radio-1',
    })
  })
})
