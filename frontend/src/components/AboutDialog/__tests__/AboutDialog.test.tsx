import { render, screen, waitFor } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { makeTheme } from '../../../theme'
import { AboutDialog } from '../AboutDialog'

function renderDialog(open: boolean) {
  return render(
    <ThemeProvider theme={makeTheme(false)}>
      <AboutDialog open={open} onClose={vi.fn()} />
    </ThemeProvider>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AboutDialog', () => {
  it('shows tagline, links, FCC note, and version when open', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)

    renderDialog(true)

    expect(screen.getByText(/self-hosted gmrs hub for your household/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /github repository/i })).toHaveAttribute(
      'href',
      'https://github.com/Xpiatio/Hearthwave'
    )
    expect(screen.getByText(/fcc part 95/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('v2.5.2')).toBeInTheDocument())
  })

  it('renders nothing visible when closed', () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)
    renderDialog(false)
    expect(screen.queryByText(/self-hosted gmrs hub/i)).not.toBeInTheDocument()
  })
})
