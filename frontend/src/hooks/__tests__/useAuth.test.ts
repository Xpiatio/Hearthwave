import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useAuth } from '../useAuth'

const TOKEN_KEY = 'auth_token'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(responses: Array<{ ok: boolean; body: unknown }>) {
  let callIndex = 0
  return vi.fn().mockImplementation(() => {
    const resp = responses[callIndex++] ?? responses[responses.length - 1]
    return Promise.resolve({
      ok: resp.ok,
      status: resp.ok ? 200 : 401,
      json: () => Promise.resolve(resp.body),
    })
  })
}

const MOCK_PROFILE = {
  id: 'user-1',
  display_name: 'Alice',
  avatar_emoji: '',
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
    spectro_colormap: 'viridis' as const,
    spectro_time_window_s: 30,
  },
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useAuth', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  // -- Initial loading state -----------------------------------------------

  it('starts in loading state', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})) // never resolves
    )
    const { result } = renderHook(() => useAuth())
    expect(result.current.loading).toBe(true)
  })

  it('clears loading after setup-status resolves with no setup needed and no stored token', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([{ ok: true, body: { setup_needed: false } }])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.token).toBeNull()
    expect(result.current.profile).toBeNull()
  })

  // -- setup_needed flag ---------------------------------------------------

  it('sets setupNeeded=true when server reports setup_needed', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([{ ok: true, body: { setup_needed: true } }])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.setupNeeded).toBe(true)
  })

  // -- Token validation on mount -------------------------------------------

  it('validates stored token on mount and sets profile when valid', async () => {
    localStorage.setItem(TOKEN_KEY, 'existing-token')
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: true, body: MOCK_PROFILE },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.token).toBe('existing-token')
    expect(result.current.profile).toEqual(MOCK_PROFILE)
  })

  it('clears stored token when /auth/me returns non-ok', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale-token')
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: false, body: { detail: 'Unauthorized' } },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.token).toBeNull()
    expect(result.current.profile).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('tolerates network failure on mount without crashing', async () => {
    localStorage.setItem(TOKEN_KEY, 'some-token')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))
    // Token kept but profile not set (network error path)
    expect(result.current.profile).toBeNull()
  })

  // -- login() -------------------------------------------------------------

  it('login: sets token and profile on success', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: true, body: { token: 'new-token', profile: MOCK_PROFILE } },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.login('Alice', 'secret')
    })

    expect(result.current.token).toBe('new-token')
    expect(result.current.profile).toEqual(MOCK_PROFILE)
    expect(localStorage.getItem(TOKEN_KEY)).toBe('new-token')
  })

  it('login: throws AuthError on failure', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: false, body: { detail: 'Bad credentials' } },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await expect(
      act(async () => {
        await result.current.login('Alice', 'wrong')
      })
    ).rejects.toMatchObject({ status: 401, detail: 'Bad credentials' })
  })

  it('login: throws with default detail when server omits it', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: false, body: {} },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await expect(
      act(async () => {
        await result.current.login('Alice', 'wrong')
      })
    ).rejects.toMatchObject({ detail: 'Login failed' })
  })

  // -- logout() ------------------------------------------------------------

  it('logout: clears token and profile', async () => {
    localStorage.setItem(TOKEN_KEY, 'session-token')
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: true, body: MOCK_PROFILE },
        { ok: true, body: {} }, // logout POST
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.token).toBeNull()
    expect(result.current.profile).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('logout: still clears state even if POST fails', async () => {
    localStorage.setItem(TOKEN_KEY, 'session-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ setup_needed: false }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(MOCK_PROFILE) })
      .mockRejectedValueOnce(new Error('Network gone'))

    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.token).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('logout: works with no stored token (skips POST)', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([{ ok: true, body: { setup_needed: false } }])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await act(async () => {
      await result.current.logout()
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  // -- setup() -------------------------------------------------------------

  it('setup: persists token and profile on success', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: true, body: { token: 'setup-token', profile: MOCK_PROFILE } },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.setup({
        display_name: 'Alice',
        password: 'pass123',
      })
    })

    expect(result.current.token).toBe('setup-token')
    expect(result.current.profile).toEqual(MOCK_PROFILE)
    expect(result.current.setupNeeded).toBe(false)
    expect(localStorage.getItem(TOKEN_KEY)).toBe('setup-token')
  })

  it('setup: throws AuthError on failure', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: false, body: { detail: 'Setup failed: name taken' } },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await expect(
      act(async () => {
        await result.current.setup({ display_name: 'Alice', password: 'pass' })
      })
    ).rejects.toMatchObject({ detail: 'Setup failed: name taken' })
  })

  // -- token persistence ---------------------------------------------------

  it('token is persisted to localStorage after login', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: true, body: { token: 'persisted-token', profile: MOCK_PROFILE } },
      ])
    )
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.login('Alice', 'secret')
    })

    expect(localStorage.getItem(TOKEN_KEY)).toBe('persisted-token')
  })

  it('token is read from localStorage on initial render', async () => {
    localStorage.setItem(TOKEN_KEY, 'pre-stored')
    vi.stubGlobal(
      'fetch',
      mockFetch([
        { ok: true, body: { setup_needed: false } },
        { ok: true, body: MOCK_PROFILE },
      ])
    )
    const { result } = renderHook(() => useAuth())
    // Before fetch settles, useState initializer should have read from localStorage
    // (token starts as pre-stored)
    expect(result.current.token).toBe('pre-stored')
    await waitFor(() => expect(result.current.loading).toBe(false))
  })
})
