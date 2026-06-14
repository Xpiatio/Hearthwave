import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect } from 'vitest'
import { makeTheme } from '../../../theme'
import { Logo } from '../Logo'

function renderLogo(ui: React.ReactElement) {
  return render(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

describe('Logo', () => {
  it('renders the mark with an accessible label', () => {
    renderLogo(<Logo />)
    expect(screen.getByRole('img', { name: /hearthwave logo/i })).toBeInTheDocument()
  })

  it('shows the wordmark when withWordmark is set', () => {
    renderLogo(<Logo withWordmark />)
    expect(screen.getByText('Hearthwave')).toBeInTheDocument()
  })

  it('omits the wordmark by default', () => {
    renderLogo(<Logo />)
    expect(screen.queryByText('Hearthwave')).not.toBeInTheDocument()
  })
})
