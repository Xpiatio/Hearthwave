import React from 'react'
import { render as rtlRender, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { LoginScreen } from '../LoginScreen'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const mockProfile = { id: 'u1', display_name: 'Alice', avatar_emoji: '👤' }

function makeFetch(profiles: typeof mockProfile[] = [mockProfile]) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(profiles),
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('LoginScreen', () => {
  describe('profile picker', () => {
    it('fetches /auth/profiles on mount and renders profile avatars', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn()
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument())
      expect(fetch).toHaveBeenCalledWith('/auth/profiles')
    })

    it('renders multiple profiles', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          { id: 'u1', display_name: 'Alice', avatar_emoji: '👤' },
          { id: 'u2', display_name: 'Bob', avatar_emoji: '🎙' },
        ]),
      }))
      render(<LoginScreen onLogin={vi.fn()} />)

      await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument())
      expect(screen.getByText('Bob')).toBeInTheDocument()
    })

    it('selects a profile on click and enables password field', async () => {
      vi.stubGlobal('fetch', makeFetch())
      render(<LoginScreen onLogin={vi.fn()} />)

      await waitFor(() => screen.getByText('Alice'))
      const profileBox = screen.getByText('Alice').closest('[style], div') as HTMLElement
      await userEvent.click(screen.getByText('Alice'))

      await waitFor(() => {
        const pwField = screen.getByLabelText(/password/i)
        expect(pwField).not.toBeDisabled()
      })
    })

    it('shows Display Name field when no profiles are returned (no-profiles fallback)', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve([]),
      }))
      render(<LoginScreen onLogin={vi.fn()} />)

      // When fetch returns ok:false, profiles stays empty
      await waitFor(() => {
        expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
      })
    })

    it('shows Display Name field when profiles array is empty', async () => {
      vi.stubGlobal('fetch', makeFetch([]))
      render(<LoginScreen onLogin={vi.fn()} />)

      await waitFor(() => {
        expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
      })
    })

    it('handles fetch error gracefully (shows fallback display name field)', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')))
      render(<LoginScreen onLogin={vi.fn()} />)

      // After fetch error, profiles stays empty → display name field shown
      await waitFor(() => {
        expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
      })
    })
  })

  describe('password form', () => {
    it('password field is disabled when no profile is selected', async () => {
      vi.stubGlobal('fetch', makeFetch())
      render(<LoginScreen onLogin={vi.fn()} />)

      await waitFor(() => screen.getByText('Alice'))
      expect(screen.getByLabelText(/password/i)).toBeDisabled()
    })

    it('submit button is disabled when password is empty', async () => {
      vi.stubGlobal('fetch', makeFetch())
      render(<LoginScreen onLogin={vi.fn()} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))

      expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled()
    })

    it('submit button is enabled when profile selected and password entered', async () => {
      vi.stubGlobal('fetch', makeFetch())
      render(<LoginScreen onLogin={vi.fn()} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'secret123')

      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled()
    })

    it('calls onLogin with display name and password on submit', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn().mockResolvedValue(undefined)
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => expect(onLogin).toHaveBeenCalledWith('Alice', 'mysecret'))
    })

    it('shows loading spinner while submitting', async () => {
      vi.stubGlobal('fetch', makeFetch())
      // onLogin that never resolves to keep loading state
      const onLogin = vi.fn().mockReturnValue(new Promise(() => {}))
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/signing in/i)).toBeInTheDocument()
      })
    })

    it('disables submit button while loading', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn().mockReturnValue(new Promise(() => {}))
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
      })
    })

    it('clears password and error when a different profile is selected', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          { id: 'u1', display_name: 'Alice', avatar_emoji: '👤' },
          { id: 'u2', display_name: 'Bob', avatar_emoji: '🎙' },
        ]),
      }))
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'bad' })
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
      await waitFor(() => screen.getByText(/invalid credentials/i))

      // Select Bob — error and password should clear
      await userEvent.click(screen.getByText('Bob'))
      await waitFor(() => {
        expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument()
      })
      expect(screen.getByLabelText(/password/i)).toHaveValue('')
    })
  })

  describe('error handling', () => {
    it('shows 401 error message on invalid credentials', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'Invalid credentials' })
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'wrongpass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
      })
    })

    it('shows network error message for unknown errors', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn().mockRejectedValue(new Error('Network failure'))
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'anypass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument()
      })
    })

    it('clears error when user starts typing password again', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'bad' })
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
      await waitFor(() => screen.getByText(/invalid credentials/i))

      await userEvent.type(screen.getByLabelText(/password/i), 'x')
      await waitFor(() => {
        expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('423 lockout', () => {
    it('shows lockout warning with parsed time when 423 with ISO timestamp', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const lockoutTime = '2026-06-02T15:30:00Z'
      const onLogin = vi.fn().mockRejectedValue({
        status: 423,
        detail: `Account locked until ${lockoutTime}`,
      })
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'anypass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/account locked until/i)).toBeInTheDocument()
        expect(screen.getByText(/contact an admin/i)).toBeInTheDocument()
      })
    })

    it('shows "a short time" lockout when 423 detail has no ISO timestamp', async () => {
      vi.stubGlobal('fetch', makeFetch())
      const onLogin = vi.fn().mockRejectedValue({
        status: 423,
        detail: 'Account is locked.',
      })
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByText('Alice'))
      await userEvent.click(screen.getByText('Alice'))
      await userEvent.type(screen.getByLabelText(/password/i), 'anypass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/account locked until a short time/i)).toBeInTheDocument()
      })
    })
  })

  describe('no-profiles fallback (display name field)', () => {
    it('allows typing display name in text field and enables sign in with password', async () => {
      vi.stubGlobal('fetch', makeFetch([]))
      const onLogin = vi.fn().mockResolvedValue(undefined)
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByLabelText(/display name/i))
      await userEvent.type(screen.getByLabelText(/display name/i), 'Charlie')
      await userEvent.type(screen.getByLabelText(/password/i), 'mypassword')

      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled()
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => expect(onLogin).toHaveBeenCalledWith('Charlie', 'mypassword'))
    })

    it('clears error when display name changes', async () => {
      vi.stubGlobal('fetch', makeFetch([]))
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'bad' })
      render(<LoginScreen onLogin={onLogin} />)

      await waitFor(() => screen.getByLabelText(/display name/i))
      await userEvent.type(screen.getByLabelText(/display name/i), 'Charlie')
      await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
      await waitFor(() => screen.getByText(/invalid credentials/i))

      await userEvent.type(screen.getByLabelText(/display name/i), 'X')
      await waitFor(() => {
        expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('general rendering', () => {
    it('renders title and subtitle', async () => {
      vi.stubGlobal('fetch', makeFetch())
      render(<LoginScreen onLogin={vi.fn()} />)

      expect(screen.getByText('Radio-TTY')).toBeInTheDocument()
      expect(screen.getByText(/select your profile/i)).toBeInTheDocument()
    })
  })
})
