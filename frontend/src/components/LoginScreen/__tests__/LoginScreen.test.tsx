import React from 'react'
import { render as rtlRender, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { LoginScreen } from '../LoginScreen'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

describe('LoginScreen', () => {
  describe('general rendering', () => {
    it('renders title and subtitle', () => {
      render(<LoginScreen onLogin={vi.fn()} />)
      expect(screen.getByText('Radio-TTY')).toBeInTheDocument()
      expect(screen.getByText(/sign in to continue/i)).toBeInTheDocument()
    })

    it('renders username and password fields', () => {
      render(<LoginScreen onLogin={vi.fn()} />)
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    })
  })

  describe('form behavior', () => {
    it('submit button is disabled when fields are empty', () => {
      render(<LoginScreen onLogin={vi.fn()} />)
      expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled()
    })

    it('submit button is disabled when only username is filled', async () => {
      render(<LoginScreen onLogin={vi.fn()} />)
      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled()
    })

    it('submit button is disabled when only password is filled', async () => {
      render(<LoginScreen onLogin={vi.fn()} />)
      await userEvent.type(screen.getByLabelText(/password/i), 'secret')
      expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled()
    })

    it('submit button is enabled when both fields are filled', async () => {
      render(<LoginScreen onLogin={vi.fn()} />)
      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'secret123')
      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled()
    })

    it('calls onLogin with username and password on submit', async () => {
      const onLogin = vi.fn().mockResolvedValue(undefined)
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => expect(onLogin).toHaveBeenCalledWith('Alice', 'mysecret'))
    })

    it('submits on Enter key in password field', async () => {
      const onLogin = vi.fn().mockResolvedValue(undefined)
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret{Enter}')

      await waitFor(() => expect(onLogin).toHaveBeenCalledWith('Alice', 'mysecret'))
    })

    it('shows loading spinner while submitting', async () => {
      const onLogin = vi.fn().mockReturnValue(new Promise(() => {}))
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/signing in/i)).toBeInTheDocument()
      })
    })

    it('disables submit button while loading', async () => {
      const onLogin = vi.fn().mockReturnValue(new Promise(() => {}))
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'mysecret')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
      })
    })
  })

  describe('error handling', () => {
    it('shows 401 error message on invalid credentials', async () => {
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'Invalid credentials' })
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'wrongpass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
      })
    })

    it('shows network error message for unknown errors', async () => {
      const onLogin = vi.fn().mockRejectedValue(new Error('Network failure'))
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'anypass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument()
      })
    })

    it('clears error when user starts typing password again', async () => {
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'bad' })
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
      await waitFor(() => screen.getByText(/invalid credentials/i))

      await userEvent.type(screen.getByLabelText(/password/i), 'x')
      await waitFor(() => {
        expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument()
      })
    })

    it('clears error when user types in username field', async () => {
      const onLogin = vi.fn().mockRejectedValue({ status: 401, detail: 'bad' })
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
      await waitFor(() => screen.getByText(/invalid credentials/i))

      await userEvent.type(screen.getByLabelText(/username/i), 'x')
      await waitFor(() => {
        expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('423 lockout', () => {
    it('shows lockout warning with parsed time when 423 with ISO timestamp', async () => {
      const lockoutTime = '2026-06-02T15:30:00Z'
      const onLogin = vi.fn().mockRejectedValue({
        status: 423,
        detail: `Account locked until ${lockoutTime}`,
      })
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'anypass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/account locked until/i)).toBeInTheDocument()
        expect(screen.getByText(/contact an admin/i)).toBeInTheDocument()
      })
    })

    it('shows "a short time" lockout when 423 detail has no ISO timestamp', async () => {
      const onLogin = vi.fn().mockRejectedValue({
        status: 423,
        detail: 'Account is locked.',
      })
      render(<LoginScreen onLogin={onLogin} />)

      await userEvent.type(screen.getByLabelText(/username/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/password/i), 'anypass')
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/account locked until a short time/i)).toBeInTheDocument()
      })
    })
  })
})
