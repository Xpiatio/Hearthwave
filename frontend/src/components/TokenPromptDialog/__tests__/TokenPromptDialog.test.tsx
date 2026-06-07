import { render as rtlRender, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'jest-axe'
import { makeTheme } from '../../../theme'
import { TokenPromptDialog } from '../TokenPromptDialog'

const theme = makeTheme(false)

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={theme}>{ui}</ThemeProvider>
  )
}

describe('TokenPromptDialog', () => {
  describe('accessibility', () => {
    it('has no violations when open with two tokens', async () => {
      const { container } = render(
        <TokenPromptDialog
          open
          tokens={['name', 'location']}
          originalText="Hello {name} from {location}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      expect(await axe(container)).toHaveNoViolations()
    })
  })

  describe('rendering', () => {
    it('renders a field per token', () => {
      render(
        <TokenPromptDialog
          open
          tokens={['name', 'city']}
          originalText="{name} in {city}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      expect(screen.getByLabelText(/value for \{name\}/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/value for \{city\}/i)).toBeInTheDocument()
    })

    it('Send button is disabled when fields are empty', () => {
      render(
        <TokenPromptDialog
          open
          tokens={['name']}
          originalText="{name}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
    })

    it('Send button is enabled when all fields are filled', async () => {
      render(
        <TokenPromptDialog
          open
          tokens={['name']}
          originalText="{name}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      await userEvent.type(screen.getByLabelText(/value for \{name\}/i), 'Alice')
      expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled()
    })
  })

  describe('submission', () => {
    it('calls onSubmit with resolved text when Send is clicked', async () => {
      const onSubmit = vi.fn()
      render(
        <TokenPromptDialog
          open
          tokens={['name', 'location']}
          originalText="Hello {name} from {location}"
          onSubmit={onSubmit}
          onCancel={vi.fn()}
        />
      )
      await userEvent.type(screen.getByLabelText(/value for \{name\}/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/value for \{location\}/i), 'Grand Rapids')
      await userEvent.click(screen.getByRole('button', { name: /send/i }))
      await waitFor(() =>
        expect(onSubmit).toHaveBeenCalledWith('Hello Alice from Grand Rapids')
      )
    })

    it('calls onCancel when Cancel is clicked', async () => {
      const onCancel = vi.fn()
      render(
        <TokenPromptDialog
          open
          tokens={['x']}
          originalText="{x}"
          onSubmit={vi.fn()}
          onCancel={onCancel}
        />
      )
      await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
      expect(onCancel).toHaveBeenCalled()
    })
  })
})
