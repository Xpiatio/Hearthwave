import React from 'react'
import { render as rtlRender, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QuickMessages } from '../QuickMessages'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const STORAGE_KEY = 'radio_tty_quick_messages'
const DEFAULTS = ['Standing by', 'QSL', 'Copy that', 'QSY to channel {N}', 'Good signal']

beforeEach(() => {
  vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null)
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('QuickMessages', () => {
  describe('list loading', () => {
    it('loads default phrases when localStorage is empty', () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(screen.getByText('Standing by')).toBeInTheDocument()
      expect(screen.getByText('QSL')).toBeInTheDocument()
      expect(screen.getByText('Copy that')).toBeInTheDocument()
      expect(screen.getByText('Good signal')).toBeInTheDocument()
    })

    it('loads phrases from localStorage when present', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return JSON.stringify(['Hello', 'Goodbye'])
        return null
      })
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(screen.getByText('Hello')).toBeInTheDocument()
      expect(screen.getByText('Goodbye')).toBeInTheDocument()
      expect(screen.queryByText('Standing by')).not.toBeInTheDocument()
    })

    it('falls back to defaults when localStorage has invalid JSON', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return 'not-valid-json'
        return null
      })
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(screen.getByText('Standing by')).toBeInTheDocument()
    })

    it('falls back to defaults when localStorage has non-array value', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return JSON.stringify({ foo: 'bar' })
        return null
      })
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(screen.getByText('Standing by')).toBeInTheDocument()
    })

    it('persists phrases to localStorage on initial render', () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(Storage.prototype.setItem).toHaveBeenCalledWith(
        STORAGE_KEY,
        JSON.stringify(DEFAULTS)
      )
    })
  })

  describe('select a phrase', () => {
    it('calls onSelect with phrase text when button clicked', async () => {
      const onSelect = vi.fn()
      render(<QuickMessages operatorName="Alice" onSelect={onSelect} />)
      await userEvent.click(screen.getByRole('button', { name: /standing by/i }))
      expect(onSelect).toHaveBeenCalledWith('Standing by')
    })

    it('calls onSelect with exact phrase when no {Name} template', async () => {
      const onSelect = vi.fn()
      render(<QuickMessages operatorName="Alice" onSelect={onSelect} />)
      await userEvent.click(screen.getByRole('button', { name: /qsl/i }))
      expect(onSelect).toHaveBeenCalledWith('QSL')
    })
  })

  describe('{Name} template substitution', () => {
    it('displays {Name} replaced with operatorName in button label', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return JSON.stringify(['Hello {Name}'])
        return null
      })
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(screen.getByRole('button', { name: 'Hello Alice' })).toBeInTheDocument()
    })

    it('substitutes {Name} (case-insensitive) in onSelect call', async () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return JSON.stringify(['Hello {name}', 'Hi {NAME}'])
        return null
      })
      const onSelect = vi.fn()
      render(<QuickMessages operatorName="Bob" onSelect={onSelect} />)

      await userEvent.click(screen.getByRole('button', { name: 'Hello Bob' }))
      expect(onSelect).toHaveBeenCalledWith('Hello Bob')

      await userEvent.click(screen.getByRole('button', { name: 'Hi Bob' }))
      expect(onSelect).toHaveBeenCalledWith('Hi Bob')
    })

    it('uses "Operator" as fallback when operatorName is empty', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return JSON.stringify(['{Name} is ready'])
        return null
      })
      render(<QuickMessages operatorName="" onSelect={vi.fn()} />)
      expect(screen.getByRole('button', { name: 'Operator is ready' })).toBeInTheDocument()
    })

    it('passes substituted text to onSelect when operatorName is empty', async () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
        if (key === STORAGE_KEY) return JSON.stringify(['{Name} standing by'])
        return null
      })
      const onSelect = vi.fn()
      render(<QuickMessages operatorName="" onSelect={onSelect} />)
      await userEvent.click(screen.getByRole('button', { name: 'Operator standing by' }))
      expect(onSelect).toHaveBeenCalledWith('Operator standing by')
    })
  })

  describe('edit mode', () => {
    async function openEditMode() {
      await userEvent.click(screen.getByRole('button', { name: /edit quick messages/i }))
    }

    it('enters edit mode when settings icon is clicked', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      expect(screen.getByRole('button', { name: /done/i })).toBeInTheDocument()
    })

    it('exits edit mode when DONE is clicked', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.click(screen.getByRole('button', { name: /done/i }))
      expect(screen.queryByRole('button', { name: /done/i })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /edit quick messages/i })).toBeInTheDocument()
    })

    it('shows add phrase input in edit mode', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      expect(screen.getByLabelText(/add phrase/i)).toBeInTheDocument()
    })

    it('ADD button is disabled when draft is empty', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      expect(screen.getByRole('button', { name: /^add$/i })).toBeDisabled()
    })

    it('ADD button is disabled when draft is whitespace only', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), '   ')
      expect(screen.getByRole('button', { name: /^add$/i })).toBeDisabled()
    })

    it('ADD button enables when draft has non-whitespace content', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), 'New phrase')
      expect(screen.getByRole('button', { name: /^add$/i })).not.toBeDisabled()
    })

    it('adds a new phrase when ADD is clicked', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), 'New phrase')
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))

      expect(screen.getByText('New phrase')).toBeInTheDocument()
    })

    it('clears draft after adding phrase', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), 'New phrase')
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))

      expect(screen.getByLabelText(/add phrase/i)).toHaveValue('')
    })

    it('adds phrase on Enter key press in input', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), 'Enter phrase{Enter}')

      expect(screen.getByText('Enter phrase')).toBeInTheDocument()
    })

    it('trims whitespace from new phrases', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), '  Trimmed  ')
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))

      expect(screen.getByText('Trimmed')).toBeInTheDocument()
    })

    it('saves to localStorage after adding phrase', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()
      await userEvent.type(screen.getByLabelText(/add phrase/i), 'Saved phrase')
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))

      await waitFor(() => {
        const calls = (Storage.prototype.setItem as ReturnType<typeof vi.fn>).mock.calls
        const lastCall = calls[calls.length - 1]
        expect(lastCall[0]).toBe(STORAGE_KEY)
        const saved = JSON.parse(lastCall[1])
        expect(saved).toContain('Saved phrase')
      })
    })
  })

  describe('edit mode - delete', () => {
    async function openEditMode() {
      await userEvent.click(screen.getByRole('button', { name: /edit quick messages/i }))
    }

    it('removes a phrase when delete button is clicked', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      const removeButtons = screen.getAllByRole('button', { name: /remove/i })
      await userEvent.click(removeButtons[0]) // remove "Standing by"

      expect(screen.queryByText('Standing by')).not.toBeInTheDocument()
    })

    it('saves to localStorage after removing a phrase', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      const removeButtons = screen.getAllByRole('button', { name: /remove/i })
      await userEvent.click(removeButtons[0])

      await waitFor(() => {
        const calls = (Storage.prototype.setItem as ReturnType<typeof vi.fn>).mock.calls
        const lastCall = calls[calls.length - 1]
        const saved = JSON.parse(lastCall[1])
        expect(saved).not.toContain('Standing by')
      })
    })
  })

  describe('edit mode - reorder', () => {
    async function openEditMode() {
      await userEvent.click(screen.getByRole('button', { name: /edit quick messages/i }))
    }

    it('first item Move Up button is disabled', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      const upButtons = screen.getAllByRole('button', { name: /move up/i })
      expect(upButtons[0]).toBeDisabled()
    })

    it('last item Move Down button is disabled', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      const downButtons = screen.getAllByRole('button', { name: /move down/i })
      expect(downButtons[downButtons.length - 1]).toBeDisabled()
    })

    it('moves item up when Move Up clicked', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      // Click "Move up" on the second item (QSL) — should swap with Standing by
      const upButtons = screen.getAllByRole('button', { name: /move up/i })
      await userEvent.click(upButtons[1]) // second item

      const listItems = screen.getAllByRole('listitem')
      expect(within(listItems[0]).getByText('QSL')).toBeInTheDocument()
      expect(within(listItems[1]).getByText('Standing by')).toBeInTheDocument()
    })

    it('moves item down when Move Down clicked', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      // Click "Move down" on the first item (Standing by) — should swap with QSL
      const downButtons = screen.getAllByRole('button', { name: /move down/i })
      await userEvent.click(downButtons[0])

      const listItems = screen.getAllByRole('listitem')
      expect(within(listItems[0]).getByText('QSL')).toBeInTheDocument()
      expect(within(listItems[1]).getByText('Standing by')).toBeInTheDocument()
    })

    it('saves to localStorage after moving item', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      const downButtons = screen.getAllByRole('button', { name: /move down/i })
      await userEvent.click(downButtons[0])

      await waitFor(() => {
        const calls = (Storage.prototype.setItem as ReturnType<typeof vi.fn>).mock.calls
        const lastCall = calls[calls.length - 1]
        const saved = JSON.parse(lastCall[1])
        // QSL should now be before Standing by
        expect(saved.indexOf('QSL')).toBeLessThan(saved.indexOf('Standing by'))
      })
    })

    it('does not move first item up (no-op guard)', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await openEditMode()

      const listItemsBefore = screen.getAllByRole('listitem').map((li) => li.textContent)
      const upButtons = screen.getAllByRole('button', { name: /move up/i })
      // Button is disabled, but verify by checking state unchanged
      expect(upButtons[0]).toBeDisabled()
      const listItemsAfter = screen.getAllByRole('listitem').map((li) => li.textContent)
      expect(listItemsAfter).toEqual(listItemsBefore)
    })
  })

  describe('general UI', () => {
    it('renders the settings/edit button in normal mode', () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      expect(screen.getByRole('button', { name: /edit quick messages/i })).toBeInTheDocument()
    })

    it('shows QUICK MESSAGES heading in edit mode', async () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      await userEvent.click(screen.getByRole('button', { name: /edit quick messages/i }))
      expect(screen.getByText('QUICK MESSAGES')).toBeInTheDocument()
    })

    it('renders all default phrases as buttons in normal mode', () => {
      render(<QuickMessages operatorName="Alice" onSelect={vi.fn()} />)
      // QSY to channel {N} has no {Name}, so it renders as-is
      DEFAULTS.forEach((phrase) => {
        const display = phrase.replace(/{Name}/gi, 'Alice')
        expect(screen.getByRole('button', { name: display })).toBeInTheDocument()
      })
    })
  })
})
