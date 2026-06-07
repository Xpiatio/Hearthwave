import React from 'react'
import { render as rtlRender, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect } from 'vitest'
import { PanelHeader } from '../PanelHeader'

const NAVY_GRADIENT = 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)'
const BLUE_GRADIENT = 'linear-gradient(135deg, #1E4976 0%, #2563EB 100%)'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

describe('PanelHeader', () => {
  it('renders the title text', () => {
    render(<PanelHeader title="NET CONTROL STATION" gradient={BLUE_GRADIENT} />)
    expect(screen.getByText('NET CONTROL STATION')).toBeInTheDocument()
  })

  it('renders title in an element with role region via parent panel — title is visible text', () => {
    render(<PanelHeader title="JOURNALS" gradient={NAVY_GRADIENT} />)
    expect(screen.getByText('JOURNALS')).toBeVisible()
  })

  it('renders an icon when provided', () => {
    render(
      <PanelHeader
        title="CONFIGURATION"
        gradient={NAVY_GRADIENT}
        icon={<span data-testid="ph-icon" aria-hidden="true" />}
      />
    )
    expect(screen.getByTestId('ph-icon')).toBeInTheDocument()
  })

  it('renders without icon prop', () => {
    render(<PanelHeader title="ATTENDANCE" gradient={NAVY_GRADIENT} />)
    expect(screen.getByText('ATTENDANCE')).toBeInTheDocument()
  })
})
