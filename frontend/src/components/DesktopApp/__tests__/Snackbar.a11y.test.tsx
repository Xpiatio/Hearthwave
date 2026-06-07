import { render as rtlRender } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { Snackbar, Alert } from '@mui/material'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'jest-axe'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

describe('Snackbar accessibility', () => {
  it('success Snackbar has no violations', async () => {
    const { container } = render(
      <Snackbar open anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert
          onClose={vi.fn()}
          severity="success"
          aria-live="polite"
          aria-atomic="true"
          sx={{ width: '100%' }}
        >
          Journal published
        </Alert>
      </Snackbar>
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('error Snackbar has no violations', async () => {
    const { container } = render(
      <Snackbar open anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert
          onClose={vi.fn()}
          severity="error"
          aria-live="assertive"
          aria-atomic="true"
          sx={{ width: '100%' }}
        >
          Something went wrong
        </Alert>
      </Snackbar>
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
