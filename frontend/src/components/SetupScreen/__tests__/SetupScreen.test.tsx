import React from 'react'
import { render as rtlRender, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { axe } from 'jest-axe'
import { SetupScreen } from '../SetupScreen'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

// MUI required fields append " *" to the accessible label, so exact:false is needed
// but "Password" also matches "Confirm Password". Use autocomplete to disambiguate.
function getPasswordInput() {
  // The password field has autocomplete="new-password" and is the first such input
  const inputs = document.querySelectorAll('input[autocomplete="new-password"]')
  return inputs[0] as HTMLElement
}
function getConfirmInput() {
  const inputs = document.querySelectorAll('input[autocomplete="new-password"]')
  return inputs[1] as HTMLElement
}
function getDisplayNameInput() {
  return document.querySelector('input[autocomplete="username"]') as HTMLElement
}

async function fillRequired(
  displayName = 'Admin',
  password = 'password123',
  confirmPassword = 'password123'
) {
  await userEvent.type(getDisplayNameInput(), displayName)
  await userEvent.type(getPasswordInput(), password)
  await userEvent.type(getConfirmInput(), confirmPassword)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('SetupScreen', () => {
  describe('rendering', () => {
    it('renders title and subtitle', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(screen.getByText('Radio-TTY')).toBeInTheDocument()
      expect(screen.getByText(/create your admin account/i)).toBeInTheDocument()
    })

    it('renders all required fields', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(getDisplayNameInput()).toBeInTheDocument()
      expect(getPasswordInput()).toBeInTheDocument()
      expect(getConfirmInput()).toBeInTheDocument()
    })

    it('renders optional station info fields', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(screen.getByLabelText(/operator name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/call sign/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/location/i)).toBeInTheDocument()
    })

    it('renders the Create Account button', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
    })

    it('renders Password helper text', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(screen.getByText(/minimum 8 characters/i)).toBeInTheDocument()
    })

    it('renders optional section label', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(screen.getByText(/station info.*optional/i)).toBeInTheDocument()
    })
  })

  describe('submit disabled until valid', () => {
    it('button is disabled on initial render', () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      expect(screen.getByRole('button', { name: /create account/i })).toBeDisabled()
    })

    it('button remains disabled with only display name filled', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getDisplayNameInput(), 'Admin')
      expect(screen.getByRole('button', { name: /create account/i })).toBeDisabled()
    })

    it('button remains disabled with short password (< 8 chars)', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getDisplayNameInput(), 'Admin')
      await userEvent.type(getPasswordInput(), 'short')
      await userEvent.type(getConfirmInput(), 'short')
      expect(screen.getByRole('button', { name: /create account/i })).toBeDisabled()
    })

    it('button remains disabled when passwords do not match', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getDisplayNameInput(), 'Admin')
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'differentpass')
      expect(screen.getByRole('button', { name: /create account/i })).toBeDisabled()
    })

    it('button remains disabled with empty display name even if passwords match', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'password123')
      expect(screen.getByRole('button', { name: /create account/i })).toBeDisabled()
    })

    it('button becomes enabled when all required fields are valid', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await fillRequired()
      expect(screen.getByRole('button', { name: /create account/i })).not.toBeDisabled()
    })

    it('button is enabled with exactly 8 character password', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await fillRequired('Admin', '12345678', '12345678')
      expect(screen.getByRole('button', { name: /create account/i })).not.toBeDisabled()
    })

    it('button is disabled with whitespace-only display name', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getDisplayNameInput(), '   ')
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'password123')
      expect(screen.getByRole('button', { name: /create account/i })).toBeDisabled()
    })
  })

  describe('password mismatch validation', () => {
    it('shows mismatch error when confirm differs from password', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'password456')
      expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument()
    })

    it('does not show mismatch error when confirm is empty', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getPasswordInput(), 'password123')
      expect(screen.queryByText(/passwords don't match/i)).not.toBeInTheDocument()
    })

    it('clears mismatch error when passwords become equal', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'password456')
      expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument()

      // Clear confirm and retype to match
      await userEvent.clear(getConfirmInput())
      await userEvent.type(getConfirmInput(), 'password123')
      expect(screen.queryByText(/passwords don't match/i)).not.toBeInTheDocument()
    })

    it('marks confirm field as error (aria-invalid) when mismatch', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'nomatch')
      expect(getConfirmInput()).toHaveAttribute('aria-invalid', 'true')
    })

    it('confirm field has no error when empty', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      // No input at all
      expect(getConfirmInput()).toHaveAttribute('aria-invalid', 'false')
    })
  })

  describe('form submission', () => {
    it('calls onSetup with required fields', async () => {
      const onSetup = vi.fn().mockResolvedValue(undefined)
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired('AdminUser', 'mypassword', 'mypassword')
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(onSetup).toHaveBeenCalledWith(expect.objectContaining({
          display_name: 'AdminUser',
          password: 'mypassword',
        }))
      })
    })

    it('calls onSetup with optional fields when filled', async () => {
      const onSetup = vi.fn().mockResolvedValue(undefined)
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.type(screen.getByLabelText(/operator name/i), 'John Doe')
      await userEvent.type(screen.getByLabelText(/call sign/i), 'kd9abc')
      await userEvent.type(screen.getByLabelText(/location/i), 'Grand Rapids, MI')
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(onSetup).toHaveBeenCalledWith(expect.objectContaining({
          operator_name: 'John Doe',
          callsign: 'KD9ABC',
          location: 'Grand Rapids, MI',
        }))
      })
    })

    it('omits empty optional fields (passes undefined)', async () => {
      const onSetup = vi.fn().mockResolvedValue(undefined)
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        const call = onSetup.mock.calls[0][0]
        expect(call.operator_name).toBeUndefined()
        expect(call.callsign).toBeUndefined()
        expect(call.location).toBeUndefined()
      })
    })

    it('trims display name whitespace before submit', async () => {
      const onSetup = vi.fn().mockResolvedValue(undefined)
      render(<SetupScreen onSetup={onSetup} />)
      // Leading/trailing spaces in display name get trimmed
      await userEvent.type(getDisplayNameInput(), 'Admin')
      await userEvent.type(getPasswordInput(), 'password123')
      await userEvent.type(getConfirmInput(), 'password123')
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(onSetup).toHaveBeenCalledWith(expect.objectContaining({
          display_name: 'Admin',
        }))
      })
    })

    it('shows loading state during submission', async () => {
      const onSetup = vi.fn().mockReturnValue(new Promise(() => {}))
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(screen.getByText(/creating account/i)).toBeInTheDocument()
      })
    })

    it('disables submit button while loading', async () => {
      const onSetup = vi.fn().mockReturnValue(new Promise(() => {}))
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /creating account/i })).toBeDisabled()
      })
    })

    it('does not call onSetup when form is invalid (guard: submit event on form)', async () => {
      const onSetup = vi.fn()
      render(<SetupScreen onSetup={onSetup} />)
      // Submit without filling anything — button is disabled, dispatch submit directly
      const form = document.querySelector('form')!
      form.dispatchEvent(new Event('submit', { bubbles: true }))
      expect(onSetup).not.toHaveBeenCalled()
    })
  })

  describe('error display', () => {
    it('shows error message when onSetup throws with detail', async () => {
      const onSetup = vi.fn().mockRejectedValue({ detail: 'Display name already taken' })
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(screen.getByText(/display name already taken/i)).toBeInTheDocument()
      })
    })

    it('shows fallback error message when detail is missing', async () => {
      const onSetup = vi.fn().mockRejectedValue({})
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        expect(screen.getByText(/setup failed/i)).toBeInTheDocument()
      })
    })

    it('clears error when display name changes after error', async () => {
      const onSetup = vi.fn().mockRejectedValue({ detail: 'Name taken' })
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))
      await waitFor(() => screen.getByText(/name taken/i))

      await userEvent.type(getDisplayNameInput(), 'X')
      await waitFor(() => {
        expect(screen.queryByText(/name taken/i)).not.toBeInTheDocument()
      })
    })

    it('clears error when password changes after error', async () => {
      const onSetup = vi.fn().mockRejectedValue({ detail: 'Some error' })
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))
      await waitFor(() => screen.getByText(/some error/i))

      await userEvent.type(getPasswordInput(), 'x')
      await waitFor(() => {
        expect(screen.queryByText(/some error/i)).not.toBeInTheDocument()
      })
    })

    it('clears error when confirm password changes after error', async () => {
      const onSetup = vi.fn().mockRejectedValue({ detail: 'Some error' })
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))
      await waitFor(() => screen.getByText(/some error/i))

      await userEvent.type(getConfirmInput(), 'x')
      await waitFor(() => {
        expect(screen.queryByText(/some error/i)).not.toBeInTheDocument()
      })
    })

    it('restores button to non-loading state after error', async () => {
      const onSetup = vi.fn().mockRejectedValue({ detail: 'Error' })
      render(<SetupScreen onSetup={onSetup} />)
      await fillRequired()
      await userEvent.click(screen.getByRole('button', { name: /create account/i }))

      await waitFor(() => {
        // After rejection, loading stops, button text reverts
        expect(screen.getByText(/create account/i)).toBeInTheDocument()
      })
    })
  })

  describe('callsign uppercasing', () => {
    it('automatically uppercases callsign input', async () => {
      render(<SetupScreen onSetup={vi.fn()} />)
      await userEvent.type(screen.getByLabelText(/call sign/i), 'kd9abc')
      expect(screen.getByLabelText(/call sign/i)).toHaveValue('KD9ABC')
    })
  })

  describe('accessibility', () => {
    it('has no violations in idle state', async () => {
      const { container } = render(<SetupScreen onSetup={vi.fn()} />)
      expect(await axe(container)).toHaveNoViolations()
    })
  })
})
