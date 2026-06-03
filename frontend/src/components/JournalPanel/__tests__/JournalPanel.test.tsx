import { render as rtlRender, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { JournalPanel } from '../JournalPanel'
import type { JournalEntry } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const JOURNALS: JournalEntry[] = [
  {
    _file: '/journals/session-2024-01-01.md',
    title: 'Morning Net',
    exported_at: '2024-01-01T10:00:00Z',
    callsigns: ['W1AAA', 'KD9ZZZ'],
    callsigns_locations: [
      { callsign: 'W1AAA', location: 'Grand Rapids' },
      { callsign: 'KD9ZZZ', location: 'Holland' },
    ],
    transcript: 'W1AAA: Good morning net.\nKD9ZZZ: Copy.',
    summary: 'A routine morning net with two stations.',
  },
  {
    _file: '/journals/session-2024-01-02.md',
    title: 'Evening Check-In',
    exported_at: '2024-01-02T20:00:00Z',
    callsigns: ['N0CALL'],
    callsigns_locations: [{ callsign: 'N0CALL', location: 'Nowhere' }],
    transcript: '',
    summary: 'Brief evening check-in.',
  },
]

const PENDING_RESULT = {
  title: 'AI Generated Title',
  summary: 'This is an AI generated summary of the session.',
  callsigns_locations: [
    { callsign: 'W1AAA', location: 'Grand Rapids' },
  ],
}

function makeProps(overrides: Partial<Parameters<typeof JournalPanel>[0]> = {}) {
  return {
    journals: [],
    pendingResult: null,
    generating: false,
    journalError: null,
    rxTexts: [],
    rxCallsigns: [],
    onListJournals: vi.fn(),
    onGenerate: vi.fn(),
    onSave: vi.fn(),
    onDelete: vi.fn(),
    onPublish: vi.fn(),
    onDismissResult: vi.fn(),
    ...overrides,
  }
}

describe('JournalPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial render', () => {
    it('renders without crashing', () => {
      render(<JournalPanel {...makeProps()} />)
      expect(screen.getByText('JOURNALS')).toBeInTheDocument()
    })

    it('calls onListJournals on mount', () => {
      const onListJournals = vi.fn()
      render(<JournalPanel {...makeProps({ onListJournals })} />)
      expect(onListJournals).toHaveBeenCalledTimes(1)
    })

    it('shows empty journals message when no journals', () => {
      render(<JournalPanel {...makeProps()} />)
      expect(screen.getByText('No saved journals.')).toBeInTheDocument()
    })

    it('shows placeholder text when nothing selected', () => {
      render(<JournalPanel {...makeProps()} />)
      expect(screen.getByText(/select a journal or generate a new one/i)).toBeInTheDocument()
    })
  })

  describe('generate button', () => {
    it('renders GENERATE FROM SESSION button', () => {
      render(<JournalPanel {...makeProps()} />)
      expect(screen.getByRole('button', { name: /generate from session/i })).toBeInTheDocument()
    })

    it('is disabled when no rx texts', () => {
      render(<JournalPanel {...makeProps({ rxTexts: [] })} />)
      expect(screen.getByRole('button', { name: /generate from session/i })).toBeDisabled()
    })

    it('is enabled when rx texts present', () => {
      render(<JournalPanel {...makeProps({ rxTexts: ['Some message'] })} />)
      expect(screen.getByRole('button', { name: /generate from session/i })).toBeEnabled()
    })

    it('shows GENERATING when generating is true', () => {
      render(<JournalPanel {...makeProps({ generating: true, rxTexts: ['msg'] })} />)
      expect(screen.getByText('GENERATING…')).toBeInTheDocument()
    })

    it('calls onGenerate with joined texts and callsigns when clicked', () => {
      const onGenerate = vi.fn()
      render(<JournalPanel {...makeProps({
        onGenerate,
        rxTexts: ['Line one', 'Line two'],
        rxCallsigns: ['W1AAA'],
      })} />)
      fireEvent.click(screen.getByRole('button', { name: /generate from session/i }))
      expect(onGenerate).toHaveBeenCalledWith('Line one\nLine two', ['W1AAA'])
    })
  })

  describe('journal error display', () => {
    it('shows journal error alert when journalError set', () => {
      render(<JournalPanel {...makeProps({ journalError: 'Something went wrong' })} />)
      expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    })

    it('does not show error alert when no error', () => {
      render(<JournalPanel {...makeProps({ journalError: null })} />)
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe('journal list', () => {
    it('renders journal entries in the list', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      expect(screen.getByText('Morning Net')).toBeInTheDocument()
      expect(screen.getByText('Evening Check-In')).toBeInTheDocument()
    })

    it('shows export date next to title', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      expect(screen.getByText('2024-01-01')).toBeInTheDocument()
    })

    it('renders publish buttons for each journal', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      const publishBtns = screen.getAllByRole('button', { name: /publish to family journal/i })
      expect(publishBtns).toHaveLength(2)
    })

    it('renders delete buttons for each journal', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      const deleteBtns = screen.getAllByRole('button', { name: /delete journal/i })
      expect(deleteBtns).toHaveLength(2)
    })
  })

  describe('journal selection', () => {
    it('shows journal detail when journal clicked', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      fireEvent.click(screen.getByText('Morning Net'))
      expect(screen.getByText('A routine morning net with two stations.')).toBeInTheDocument()
    })

    it('shows callsigns table for selected journal', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      fireEvent.click(screen.getByText('Morning Net'))
      expect(screen.getByText('Grand Rapids')).toBeInTheDocument()
    })

    it('shows transcript accordion for selected journal with transcript', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      fireEvent.click(screen.getByText('Morning Net'))
      expect(screen.getByText('Session transcript')).toBeInTheDocument()
    })

    it('does not show transcript accordion when transcript is empty', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      fireEvent.click(screen.getByText('Evening Check-In'))
      expect(screen.queryByText('Session transcript')).not.toBeInTheDocument()
    })

    it('calls onDismissResult when journal clicked', () => {
      const onDismissResult = vi.fn()
      render(<JournalPanel {...makeProps({ journals: JOURNALS, onDismissResult })} />)
      fireEvent.click(screen.getByText('Morning Net'))
      expect(onDismissResult).toHaveBeenCalledTimes(1)
    })
  })

  describe('delete flow', () => {
    it('first delete click changes button label to Confirm delete', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      const deleteBtn = screen.getAllByRole('button', { name: /delete journal/i })[0]
      fireEvent.click(deleteBtn)
      expect(screen.getByRole('button', { name: /confirm delete/i })).toBeInTheDocument()
    })

    it('second delete click calls onDelete with file path', () => {
      const onDelete = vi.fn()
      render(<JournalPanel {...makeProps({ journals: JOURNALS, onDelete })} />)
      const deleteBtn = screen.getAllByRole('button', { name: /delete journal/i })[0]
      fireEvent.click(deleteBtn)
      fireEvent.click(screen.getByRole('button', { name: /confirm delete/i }))
      expect(onDelete).toHaveBeenCalledWith('/journals/session-2024-01-01.md')
    })

    it('first delete click does not call onDelete', () => {
      const onDelete = vi.fn()
      render(<JournalPanel {...makeProps({ journals: JOURNALS, onDelete })} />)
      const deleteBtn = screen.getAllByRole('button', { name: /delete journal/i })[0]
      fireEvent.click(deleteBtn)
      expect(onDelete).not.toHaveBeenCalled()
    })
  })

  describe('publish flow', () => {
    it('first publish click changes button label to Confirm publish', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      const publishBtn = screen.getAllByRole('button', { name: /publish to family journal/i })[0]
      fireEvent.click(publishBtn)
      expect(screen.getByRole('button', { name: /confirm publish/i })).toBeInTheDocument()
    })

    it('second publish click calls onPublish with file path', () => {
      const onPublish = vi.fn()
      render(<JournalPanel {...makeProps({ journals: JOURNALS, onPublish })} />)
      const publishBtn = screen.getAllByRole('button', { name: /publish to family journal/i })[0]
      fireEvent.click(publishBtn)
      fireEvent.click(screen.getByRole('button', { name: /confirm publish/i }))
      expect(onPublish).toHaveBeenCalledWith('/journals/session-2024-01-01.md')
    })

    it('auto-cancels publish confirm after 4 seconds', () => {
      render(<JournalPanel {...makeProps({ journals: JOURNALS })} />)
      const publishBtn = screen.getAllByRole('button', { name: /publish to family journal/i })[0]
      fireEvent.click(publishBtn)
      expect(screen.getByRole('button', { name: /confirm publish/i })).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(4000) })
      expect(screen.queryByRole('button', { name: /confirm publish/i })).not.toBeInTheDocument()
    })
  })

  describe('pending result (AI draft)', () => {
    it('shows AI draft view when pendingResult provided', () => {
      render(<JournalPanel {...makeProps({ pendingResult: PENDING_RESULT })} />)
      expect(screen.getByText('AI DRAFT — REVIEW AND SAVE')).toBeInTheDocument()
    })

    it('populates title from pendingResult', () => {
      render(<JournalPanel {...makeProps({ pendingResult: PENDING_RESULT })} />)
      expect(screen.getByDisplayValue('AI Generated Title')).toBeInTheDocument()
    })

    it('populates summary from pendingResult', () => {
      render(<JournalPanel {...makeProps({ pendingResult: PENDING_RESULT })} />)
      expect(screen.getByDisplayValue('This is an AI generated summary of the session.')).toBeInTheDocument()
    })

    it('shows callsigns table in draft', () => {
      render(<JournalPanel {...makeProps({ pendingResult: PENDING_RESULT })} />)
      expect(screen.getByText('Grand Rapids')).toBeInTheDocument()
    })

    it('calls onSave and onDismissResult when SAVE JOURNAL clicked', () => {
      const onSave = vi.fn()
      const onDismissResult = vi.fn()
      render(<JournalPanel {...makeProps({ pendingResult: PENDING_RESULT, onSave, onDismissResult, rxTexts: ['msg'] })} />)
      fireEvent.click(screen.getByRole('button', { name: /save journal/i }))
      expect(onSave).toHaveBeenCalledTimes(1)
      expect(onDismissResult).toHaveBeenCalledTimes(1)
    })

    it('SAVE JOURNAL is disabled when title is empty', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      const pendingNoTitle = { ...PENDING_RESULT, title: '' }
      render(<JournalPanel {...makeProps({ pendingResult: pendingNoTitle })} />)
      expect(screen.getByRole('button', { name: /save journal/i })).toBeDisabled()
    })

    it('calls onDismissResult when DISCARD clicked', () => {
      const onDismissResult = vi.fn()
      render(<JournalPanel {...makeProps({ pendingResult: PENDING_RESULT, onDismissResult })} />)
      fireEvent.click(screen.getByRole('button', { name: /discard/i }))
      expect(onDismissResult).toHaveBeenCalledTimes(1)
    })

    it('does not show callsigns table when callsigns_locations is empty', () => {
      const pendingNoCallsigns = { ...PENDING_RESULT, callsigns_locations: [] }
      render(<JournalPanel {...makeProps({ pendingResult: pendingNoCallsigns })} />)
      // No table should be in the right panel (only in pending result area)
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
    })
  })

  describe('journal title fallback', () => {
    it('shows (untitled) for journals with empty title', () => {
      const journals = [{ ...JOURNALS[0], title: '' }]
      render(<JournalPanel {...makeProps({ journals })} />)
      expect(screen.getByText('(untitled)')).toBeInTheDocument()
    })
  })
})
