import React from 'react'
import { render as rtlRender, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { ButtonEditorDialog } from '../ButtonEditorDialog'

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ButtonEditorDialog', () => {
  it('creating a new button requires a label', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <ButtonEditorDialog open button={null} onSave={onSave} onDelete={vi.fn()} onClose={vi.fn()} />
    )
    expect(screen.getByRole('button', { name: 'SAVE' })).toBeDisabled()
    await user.type(screen.getByRole('textbox', { name: /Label/ }), 'Water')
    await user.click(screen.getByRole('button', { name: 'SAVE' }))
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave.mock.calls[0][0]).toMatchObject({ label: 'Water', text: 'Water' })
    expect(onSave.mock.calls[0][0].id).toBeTruthy()
  })

  it('editing keeps the id and saves changed fields', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    const button = { id: 'b1', emoji: '👍', label: 'Yes', text: 'Yes' }
    render(
      <ButtonEditorDialog open button={button} onSave={onSave} onDelete={vi.fn()} onClose={vi.fn()} />
    )
    const text = screen.getByRole('textbox', { name: /Spoken text/ })
    await user.clear(text)
    await user.type(text, 'Affirmative')
    await user.click(screen.getByRole('button', { name: 'SAVE' }))
    expect(onSave).toHaveBeenCalledWith({ id: 'b1', emoji: '👍', label: 'Yes', text: 'Affirmative' })
  })

  it('delete asks for confirmation then calls onDelete', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    const button = { id: 'b1', emoji: '👍', label: 'Yes', text: 'Yes' }
    render(
      <ButtonEditorDialog open button={button} onSave={vi.fn()} onDelete={onDelete} onClose={vi.fn()} />
    )
    await user.click(screen.getByRole('button', { name: 'DELETE' }))
    expect(onDelete).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /yes, delete it/i }))
    expect(onDelete).toHaveBeenCalledWith('b1')
  })

  it('does NOT call onDelete when the delete confirmation is declined', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    const button = { id: 'b1', emoji: '👍', label: 'Yes', text: 'Yes' }
    render(
      <ButtonEditorDialog open button={button} onSave={vi.fn()} onDelete={onDelete} onClose={vi.fn()} />
    )
    await user.click(screen.getByRole('button', { name: 'DELETE' }))
    await user.click(screen.getByRole('button', { name: /no, go back/i }))
    expect(onDelete).not.toHaveBeenCalled()
  })
})
