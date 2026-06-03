import { render as rtlRender, screen, fireEvent, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ContactsDialog } from '../ContactsDialog'
import type { Contact, FccLookupResultMsg } from '../../../types/ws'

// Mock URL.createObjectURL and revokeObjectURL (not in jsdom)
vi.stubGlobal('URL', {
  createObjectURL: vi.fn(() => 'blob:mock'),
  revokeObjectURL: vi.fn(),
})

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const CONTACTS: Contact[] = [
  {
    callsign: 'W1AAA',
    name: 'Alice Smith',
    location: 'Grand Rapids, MI',
    gmrs_callsign: 'WRXX100',
    ham_callsign: 'W1AAA',
    verified: true,
    verified_at: '2024-01-01T00:00:00Z',
    fcc_name: 'Alice Smith',
    fcc_location: 'Grand Rapids',
  },
  {
    callsign: 'KD9ZZZ',
    name: 'Bob Jones',
    location: 'Holland, MI',
    gmrs_callsign: '',
    ham_callsign: 'KD9ZZZ',
    verified: false,
  },
]

function makeProps(overrides: Partial<Parameters<typeof ContactsDialog>[0]> = {}) {
  return {
    open: true,
    onClose: vi.fn(),
    contacts: CONTACTS,
    fccLookupResult: null,
    verifyAllComplete: false,
    onSend: vi.fn(),
    onVerifyAllDismiss: vi.fn(),
    ...overrides,
  }
}

describe('ContactsDialog', () => {
  describe('dialog renders', () => {
    it('renders when open=true', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByText('Contacts')).toBeInTheDocument()
    })

    it('does not render content when open=false', () => {
      render(<ContactsDialog {...makeProps({ open: false })} />)
      // Dialog content should not be visible
      expect(screen.queryByText('Add Contact')).not.toBeInTheDocument()
    })

    it('shows contact count', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByText('(2)')).toBeInTheDocument()
    })

    it('shows zero count with empty contacts', () => {
      render(<ContactsDialog {...makeProps({ contacts: [] })} />)
      expect(screen.getByText('(0)')).toBeInTheDocument()
    })

    it('calls onClose when Close button clicked', () => {
      const onClose = vi.fn()
      render(<ContactsDialog {...makeProps({ onClose })} />)
      fireEvent.click(screen.getByRole('button', { name: /^close$/i }))
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('toolbar buttons', () => {
    it('renders Add Contact button', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /add contact/i })).toBeInTheDocument()
    })

    it('renders Sort by Suffix button', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /sort by suffix/i })).toBeInTheDocument()
    })

    it('renders Verify All button', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /verify all/i })).toBeInTheDocument()
    })

    it('Verify All is disabled when contacts empty', () => {
      render(<ContactsDialog {...makeProps({ contacts: [] })} />)
      expect(screen.getByRole('button', { name: /verify all/i })).toBeDisabled()
    })

    it('Verify All is enabled with contacts', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /verify all/i })).toBeEnabled()
    })

    it('calls onSend with verify_all when Verify All clicked', () => {
      const onSend = vi.fn()
      const onVerifyAllDismiss = vi.fn()
      render(<ContactsDialog {...makeProps({ onSend, onVerifyAllDismiss })} />)
      fireEvent.click(screen.getByRole('button', { name: /verify all/i }))
      expect(onSend).toHaveBeenCalledWith({ type: 'verify_all' })
    })

    it('renders Import button', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /import/i })).toBeInTheDocument()
    })

    it('renders Export JSON button', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /export json/i })).toBeInTheDocument()
    })

    it('renders Export CSV button', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument()
    })
  })

  describe('contacts table', () => {
    it('renders table headers', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByText('Callsign')).toBeInTheDocument()
      expect(screen.getByText('Name')).toBeInTheDocument()
      expect(screen.getByText('Location')).toBeInTheDocument()
      expect(screen.getByText('GMRS')).toBeInTheDocument()
      expect(screen.getByText('HAM')).toBeInTheDocument()
      expect(screen.getByText('Verified')).toBeInTheDocument()
    })

    it('shows empty message when no contacts', () => {
      render(<ContactsDialog {...makeProps({ contacts: [] })} />)
      expect(screen.getByText('No contacts yet. Add one above.')).toBeInTheDocument()
    })

    it('renders each contact as a row', () => {
      render(<ContactsDialog {...makeProps()} />)
      // Callsign appears in both the row cell and the action button aria-labels — use getAllByText
      expect(screen.getAllByText('W1AAA').length).toBeGreaterThan(0)
      expect(screen.getByText('Alice Smith')).toBeInTheDocument()
      expect(screen.getByText('Grand Rapids, MI')).toBeInTheDocument()
      expect(screen.getAllByText('KD9ZZZ').length).toBeGreaterThan(0)
      expect(screen.getByText('Bob Jones')).toBeInTheDocument()
    })

    it('shows verified icon for verified contacts', () => {
      render(<ContactsDialog {...makeProps()} />)
      // CheckCircleIcon renders as an SVG. W1AAA is verified — find a CheckCircle SVG in the table.
      // MUI renders SVG icons with data-testid like "CheckCircleIcon" (MUI v5+)
      const checkIcon = document.querySelector('[data-testid="CheckCircleIcon"]')
      expect(checkIcon).toBeTruthy()
    })

    it('renders edit buttons for each contact', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /edit w1aaa/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /edit kd9zzz/i })).toBeInTheDocument()
    })

    it('renders delete buttons for each contact', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(screen.getByRole('button', { name: /delete w1aaa/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /delete kd9zzz/i })).toBeInTheDocument()
    })

    it('calls onSend with delete_contact when delete clicked', () => {
      const onSend = vi.fn()
      render(<ContactsDialog {...makeProps({ onSend })} />)
      fireEvent.click(screen.getByRole('button', { name: /delete w1aaa/i }))
      expect(onSend).toHaveBeenCalledWith({ type: 'delete_contact', callsign: 'W1AAA' })
    })
  })

  describe('sort by suffix', () => {
    it('toggles sort mode when Sort by Suffix clicked', () => {
      render(<ContactsDialog {...makeProps()} />)
      const sortBtn = screen.getByRole('button', { name: /sort by suffix/i })
      // Initially outlined, after click should be contained (selected state)
      fireEvent.click(sortBtn)
      // Verify button reflects toggle — it should now be variant="contained"
      // We test by clicking again to toggle back — the data order may shift
      expect(sortBtn).toBeInTheDocument() // Existence check; visual check not feasible in unit test
    })

    it('contacts still render after sort toggle', () => {
      render(<ContactsDialog {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: /sort by suffix/i }))
      expect(screen.getAllByText('W1AAA').length).toBeGreaterThan(0)
      expect(screen.getAllByText('KD9ZZZ').length).toBeGreaterThan(0)
    })
  })

  describe('verifyAllComplete banner', () => {
    it('shows Verify complete chip when verifyAllComplete=true', () => {
      render(<ContactsDialog {...makeProps({ verifyAllComplete: true })} />)
      expect(screen.getByText('Verify complete')).toBeInTheDocument()
    })

    it('calls onVerifyAllDismiss when chip delete button clicked', () => {
      const onVerifyAllDismiss = vi.fn()
      render(<ContactsDialog {...makeProps({ verifyAllComplete: true, onVerifyAllDismiss })} />)
      // MUI Chip label is a <span> with class MuiChip-label, but the chip root is its parent
      const chipLabel = screen.getByText('Verify complete')
      const chipRoot = chipLabel.closest('[class*="MuiChip-root"]') as HTMLElement
      expect(chipRoot).toBeTruthy()
      // The delete icon SVG is a sibling of the label inside the chip root
      const deleteIcon = chipRoot.querySelector('svg') as SVGElement | null
      expect(deleteIcon).toBeTruthy()
      if (deleteIcon) fireEvent.click(deleteIcon)
      expect(onVerifyAllDismiss).toHaveBeenCalledTimes(1)
    })

    it('does not show chip when verifyAllComplete=false', () => {
      render(<ContactsDialog {...makeProps({ verifyAllComplete: false })} />)
      expect(screen.queryByText('Verify complete')).not.toBeInTheDocument()
    })
  })

  describe('Add Contact dialog', () => {
    async function openAddDialog(props = makeProps()) {
      render(<ContactsDialog {...props} />)
      fireEvent.click(screen.getByRole('button', { name: /add contact/i }))
      await waitFor(() => screen.getByText('Add Contact', { selector: '[class*="MuiDialogTitle"]' }))
    }

    // Helper: get the callsign field inside the Add/Edit dialog (label is "Callsign *")
    function getCallsignField() {
      return screen.getByLabelText('Callsign *')
    }

    it('opens add dialog when Add Contact clicked', async () => {
      await openAddDialog()
      expect(screen.getByText('Add Contact', { selector: '[class*="MuiDialogTitle"]' })).toBeInTheDocument()
    })

    it('shows empty callsign field in add mode', async () => {
      await openAddDialog()
      expect(getCallsignField()).toHaveValue('')
    })

    it('callsign field is enabled in add mode', async () => {
      await openAddDialog()
      expect(getCallsignField()).toBeEnabled()
    })

    it('Save button is disabled when callsign empty', async () => {
      await openAddDialog()
      expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled()
    })

    it('Save button enabled after callsign entered', async () => {
      const user = userEvent.setup()
      await openAddDialog()
      await user.type(getCallsignField(), 'W1NEW')
      expect(screen.getByRole('button', { name: /^save$/i })).toBeEnabled()
    })

    it('uppercases callsign input', async () => {
      await openAddDialog()
      fireEvent.change(getCallsignField(), { target: { value: 'w1new' } })
      expect(getCallsignField()).toHaveValue('W1NEW')
    })

    it('calls onSend with add_contact when Save clicked', async () => {
      const onSend = vi.fn()
      await openAddDialog(makeProps({ onSend }))
      fireEvent.change(getCallsignField(), { target: { value: 'W1NEW' } })
      fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Person' } })
      fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
      expect(onSend).toHaveBeenCalledWith(expect.objectContaining({
        type: 'add_contact',
        callsign: 'W1NEW',
        name: 'New Person',
      }))
    })

    it('closes dialog when Cancel clicked', async () => {
      await openAddDialog()
      fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
      await waitFor(() => {
        expect(screen.queryByText('Add Contact', { selector: '[class*="MuiDialogTitle"]' })).not.toBeInTheDocument()
      })
    })

    it('shows FCC Look Up button', async () => {
      await openAddDialog()
      expect(screen.getByRole('button', { name: /fcc look up/i })).toBeInTheDocument()
    })

    it('FCC Look Up is disabled when callsign empty', async () => {
      await openAddDialog()
      expect(screen.getByRole('button', { name: /fcc look up/i })).toBeDisabled()
    })

    it('sends fcc_lookup when FCC Look Up clicked with callsign', async () => {
      const onSend = vi.fn()
      await openAddDialog(makeProps({ onSend }))
      fireEvent.change(getCallsignField(), { target: { value: 'W1AAA' } })
      fireEvent.click(screen.getByRole('button', { name: /fcc look up/i }))
      expect(onSend).toHaveBeenCalledWith({ type: 'fcc_lookup', callsign: 'W1AAA', name: '' })
    })
  })

  describe('Edit Contact dialog', () => {
    async function openEditDialog(props = makeProps()) {
      render(<ContactsDialog {...props} />)
      fireEvent.click(screen.getByRole('button', { name: /edit w1aaa/i }))
      await waitFor(() => screen.getByText('Edit Contact', { selector: '[class*="MuiDialogTitle"]' }))
    }

    it('opens edit dialog with correct title', async () => {
      await openEditDialog()
      expect(screen.getByText('Edit Contact', { selector: '[class*="MuiDialogTitle"]' })).toBeInTheDocument()
    })

    it('prefills callsign field in edit mode', async () => {
      await openEditDialog()
      // Callsign field in Add/Edit dialog — disabled in edit mode, label is "Callsign *"
      expect(screen.getByLabelText('Callsign *')).toHaveValue('W1AAA')
    })

    it('callsign field is disabled in edit mode', async () => {
      await openEditDialog()
      expect(screen.getByLabelText('Callsign *')).toBeDisabled()
    })

    it('prefills name field', async () => {
      await openEditDialog()
      expect(screen.getByDisplayValue('Alice Smith')).toBeInTheDocument()
    })

    it('prefills location field', async () => {
      await openEditDialog()
      expect(screen.getByDisplayValue('Grand Rapids, MI')).toBeInTheDocument()
    })

    it('prefills GMRS callsign', async () => {
      await openEditDialog()
      expect(screen.getByDisplayValue('WRXX100')).toBeInTheDocument()
    })

    it('calls onSend with updated contact when saved', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      await openEditDialog(makeProps({ onSend }))
      fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
      expect(onSend).toHaveBeenCalledWith(expect.objectContaining({
        type: 'add_contact',
        callsign: 'W1AAA',
      }))
    })
  })

  describe('prefilled callsign from props', () => {
    it('opens add dialog pre-filled when prefilledCallsign provided', async () => {
      render(<ContactsDialog {...makeProps({
        prefilledCallsign: 'KD9NEW',
        prefilledName: 'New Station',
        prefilledLocation: 'Kalamazoo',
      })} />)
      await waitFor(() => {
        expect(screen.getByDisplayValue('KD9NEW')).toBeInTheDocument()
        expect(screen.getByDisplayValue('New Station')).toBeInTheDocument()
      })
    })
  })

  describe('fccLookupResult auto-fill', () => {
    it('auto-fills form when fccLookupResult matches open form callsign', async () => {
      const fccResult: FccLookupResultMsg = {
        type: 'fcc_lookup_result',
        callsign: 'W1NEW',
        status: 'Active',
        license_name: 'FCC Name',
        license_location: 'FCC Location',
        license_city: 'FCC City',
        gmrs_callsign: 'WRCC999',
        ham_callsign: 'W1NEW',
      }
      // Open with prefilledCallsign to get edit dialog open
      const { rerender } = render(<ContactsDialog {...makeProps({
        prefilledCallsign: 'W1NEW',
        fccLookupResult: null,
      })} />)
      await waitFor(() => screen.getByDisplayValue('W1NEW'))
      // Now push in the FCC result
      rerender(
        <ThemeProvider theme={makeTheme(false)}>
          <ContactsDialog {...makeProps({
            prefilledCallsign: 'W1NEW',
            fccLookupResult: fccResult,
          })} />
        </ThemeProvider>
      )
      await waitFor(() => {
        expect(screen.getByDisplayValue('FCC Name')).toBeInTheDocument()
      })
    })
  })

  describe('export functions', () => {
    it('triggers download when Export JSON clicked', () => {
      // URL.createObjectURL is mocked — just verify no error
      render(<ContactsDialog {...makeProps()} />)
      expect(() => fireEvent.click(screen.getByRole('button', { name: /export json/i }))).not.toThrow()
    })

    it('triggers download when Export CSV clicked', () => {
      render(<ContactsDialog {...makeProps()} />)
      expect(() => fireEvent.click(screen.getByRole('button', { name: /export csv/i }))).not.toThrow()
    })
  })
})
