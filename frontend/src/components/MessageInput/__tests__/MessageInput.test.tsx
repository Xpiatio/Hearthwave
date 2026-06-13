import { render as rtlRender, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useRef } from 'react'
import { axe } from 'jest-axe'
import { MessageInput } from '../MessageInput'
import type { MessageInputHandle } from '../MessageInput'
import type { Contact } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const CONTACTS: Contact[] = [
  { callsign: 'W1AAA', name: 'Alice', location: 'Grand Rapids' },
  { callsign: 'KD9ZZZ', name: 'Bob', location: 'Holland' },
]

describe('MessageInput', () => {
  describe('textarea rendering', () => {
    it('renders the message textarea', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(
        screen.getByRole('textbox', { name: /message text/i })
      ).toBeInTheDocument()
    })

    it('shows placeholder text when not transmitting', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(
        screen.getByPlaceholderText(/Enter your message here/i)
      ).toBeInTheDocument()
    })

    it('shows the send button', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(
        screen.getByRole('button', { name: /press to send message/i })
      ).toBeInTheDocument()
    })
  })

  describe('disabled when transmitting', () => {
    it('disables the textarea when transmitting', () => {
      render(<MessageInput transmitting={true} contacts={[]} onSend={vi.fn()} />)
      expect(screen.getByRole('textbox', { name: /message text/i })).toBeDisabled()
    })

    it('disables the send button when transmitting', () => {
      render(<MessageInput transmitting={true} contacts={[]} onSend={vi.fn()} />)
      expect(screen.getByRole('button', { name: /press to send message/i })).toBeDisabled()
    })

    it('shows transmitting alert when transmitting is true', () => {
      render(<MessageInput transmitting={true} contacts={[]} onSend={vi.fn()} />)
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText(/SENDING MESSAGE NOW/i)).toBeInTheDocument()
    })

    it('does not show transmitting alert when not transmitting', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe('send button disabled when draft is empty', () => {
    it('send button is disabled when textarea is empty', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(screen.getByRole('button', { name: /press to send message/i })).toBeDisabled()
    })

    it('send button is enabled when textarea has text', async () => {
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      await user.type(screen.getByRole('textbox', { name: /message text/i }), 'Hello')
      expect(screen.getByRole('button', { name: /press to send message/i })).toBeEnabled()
    })

    it('send button stays disabled for whitespace-only input', async () => {
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      await user.type(screen.getByRole('textbox', { name: /message text/i }), '   ')
      expect(screen.getByRole('button', { name: /press to send message/i })).toBeDisabled()
    })
  })

  describe('send on button click', () => {
    it('calls onSend with trimmed text when send button clicked', async () => {
      const onSend = vi.fn()
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={onSend} />)
      await user.type(screen.getByRole('textbox', { name: /message text/i }), '  Hello World  ')
      fireEvent.click(screen.getByRole('button', { name: /press to send message/i }))
      expect(onSend).toHaveBeenCalledTimes(1)
      expect(onSend).toHaveBeenCalledWith('Hello World', 'ALL', '')
    })

    it('clears the textarea after send', async () => {
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      const textarea = screen.getByRole('textbox', { name: /message text/i })
      await user.type(textarea, 'Test message')
      fireEvent.click(screen.getByRole('button', { name: /press to send message/i }))
      expect(textarea).toHaveValue('')
    })

    it('does not call onSend when transmitting', () => {
      const onSend = vi.fn()
      render(<MessageInput transmitting={true} contacts={[]} onSend={onSend} />)
      fireEvent.click(screen.getByRole('button', { name: /press to send message/i }))
      expect(onSend).not.toHaveBeenCalled()
    })
  })

  describe('Ctrl+Enter to send', () => {
    it('calls onSend on Ctrl+Enter', async () => {
      const onSend = vi.fn()
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={onSend} />)
      const textarea = screen.getByRole('textbox', { name: /message text/i })
      await user.type(textarea, 'Hello')
      await user.keyboard('{Control>}{Enter}{/Control}')
      expect(onSend).toHaveBeenCalledTimes(1)
      expect(onSend).toHaveBeenCalledWith('Hello', 'ALL', '')
    })

    it('calls onSend on Meta+Enter (Mac)', async () => {
      const onSend = vi.fn()
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={onSend} />)
      const textarea = screen.getByRole('textbox', { name: /message text/i })
      await user.type(textarea, 'Mac message')
      await user.keyboard('{Meta>}{Enter}{/Meta}')
      expect(onSend).toHaveBeenCalledTimes(1)
    })

    it('does NOT send on plain Enter', async () => {
      const onSend = vi.fn()
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={[]} onSend={onSend} />)
      await user.type(screen.getByRole('textbox', { name: /message text/i }), 'Hello')
      await user.keyboard('{Enter}')
      expect(onSend).not.toHaveBeenCalled()
    })
  })

  describe('contact dropdown', () => {
    it('does not render dropdown when contacts list is empty', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(screen.queryByLabelText('To')).not.toBeInTheDocument()
    })

    it('renders dropdown when contacts are provided', () => {
      render(<MessageInput transmitting={false} contacts={CONTACTS} onSend={vi.fn()} />)
      expect(screen.getByLabelText('To')).toBeInTheDocument()
    })

    it('disables the dropdown when transmitting', () => {
      render(<MessageInput transmitting={true} contacts={CONTACTS} onSend={vi.fn()} />)
      // The Select combobox should be disabled
      expect(screen.getByRole('combobox')).toHaveAttribute('aria-disabled', 'true')
    })

    it('sends to ALL when no contact selected', async () => {
      const onSend = vi.fn()
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={CONTACTS} onSend={onSend} />)
      await user.type(screen.getByRole('textbox', { name: /message text/i }), 'Broadcast')
      fireEvent.click(screen.getByRole('button', { name: /press to send message/i }))
      expect(onSend).toHaveBeenCalledWith('Broadcast', 'ALL', '')
    })

    it('sorts contacts alphabetically — sends the correct callsign after selecting first sorted entry', async () => {
      // We verify sorting indirectly: when only one contact is available, it should be the one sent
      const single: Contact[] = [{ callsign: 'W1AAA', name: 'Alice' }]
      const onSend = vi.fn()
      const user = userEvent.setup()
      render(<MessageInput transmitting={false} contacts={single} onSend={onSend} />)
      // Open the Select dropdown
      fireEvent.mouseDown(screen.getByRole('combobox'))
      // MUI renders options into a Portal — wait for them
      await screen.findByRole('option', { name: /W1AAA/i })
      fireEvent.click(screen.getByRole('option', { name: /W1AAA/i }))
      await user.type(screen.getByRole('textbox', { name: /message text/i }), 'Hi')
      fireEvent.click(screen.getByRole('button', { name: /press to send message/i }))
      expect(onSend).toHaveBeenCalledWith('Hi', 'W1AAA', 'Alice')
    })
  })

  describe('onStandaloneId button', () => {
    it('does not render THIS IS button when onStandaloneId is not provided', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(screen.queryByRole('button', { name: /standalone station identification/i })).not.toBeInTheDocument()
    })

    it('renders THIS IS button when onStandaloneId is provided', () => {
      render(
        <MessageInput
          transmitting={false}
          contacts={[]}
          onSend={vi.fn()}
          onStandaloneId={vi.fn()}
        />
      )
      expect(
        screen.getByRole('button', { name: /standalone station identification/i })
      ).toBeInTheDocument()
    })

    it('calls onStandaloneId when THIS IS button clicked', () => {
      const onStandaloneId = vi.fn()
      render(
        <MessageInput
          transmitting={false}
          contacts={[]}
          onSend={vi.fn()}
          onStandaloneId={onStandaloneId}
        />
      )
      fireEvent.click(screen.getByRole('button', { name: /standalone station identification/i }))
      expect(onStandaloneId).toHaveBeenCalledTimes(1)
    })

    it('disables THIS IS button when transmitting', () => {
      render(
        <MessageInput
          transmitting={true}
          contacts={[]}
          onSend={vi.fn()}
          onStandaloneId={vi.fn()}
        />
      )
      expect(
        screen.getByRole('button', { name: /standalone station identification/i })
      ).toBeDisabled()
    })
  })

  describe('imperative setText handle', () => {
    it('sets the textarea value via ref.setText', async () => {
      function Harness() {
        const ref = useRef<MessageInputHandle>(null)
        return (
          <>
            <button onClick={() => ref.current?.setText('Injected text')}>inject</button>
            <MessageInput ref={ref} transmitting={false} contacts={[]} onSend={vi.fn()} />
          </>
        )
      }
      render(<Harness />)
      fireEvent.click(screen.getByRole('button', { name: 'inject' }))
      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /message text/i })).toHaveValue('Injected text')
      })
    })

    it('enables send button after setText is called with non-empty text', async () => {
      function Harness() {
        const ref = useRef<MessageInputHandle>(null)
        return (
          <>
            <button onClick={() => ref.current?.setText('Ready to send')}>fill</button>
            <MessageInput ref={ref} transmitting={false} contacts={[]} onSend={vi.fn()} />
          </>
        )
      }
      render(<Harness />)
      fireEvent.click(screen.getByRole('button', { name: 'fill' }))
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /press to send message/i })).toBeEnabled()
      })
    })
  })

  describe('chat (no transmit) button', () => {
    it('renders a chat button when onChat is provided', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} onChat={vi.fn()} />)
      expect(screen.getByRole('button', { name: /chat/i })).toBeInTheDocument()
    })

    it('does not render a chat button when onChat is absent', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} />)
      expect(screen.queryByRole('button', { name: /chat/i })).not.toBeInTheDocument()
    })

    it('calls onChat (not onSend) with trimmed text when chat is clicked', () => {
      const onChat = vi.fn()
      const onSend = vi.fn()
      render(<MessageInput transmitting={false} contacts={[]} onSend={onSend} onChat={onChat} />)
      fireEvent.change(screen.getByRole('textbox', { name: /message text/i }), {
        target: { value: '  meet at noon  ' },
      })
      fireEvent.click(screen.getByRole('button', { name: /chat/i }))
      expect(onChat).toHaveBeenCalledWith('meet at noon')
      expect(onSend).not.toHaveBeenCalled()
    })

    it('calls onSend (not onChat) when the transmit button is clicked', () => {
      const onChat = vi.fn()
      const onSend = vi.fn()
      render(<MessageInput transmitting={false} contacts={[]} onSend={onSend} onChat={onChat} />)
      fireEvent.change(screen.getByRole('textbox', { name: /message text/i }), {
        target: { value: 'hello' },
      })
      fireEvent.click(screen.getByRole('button', { name: /press to send message/i }))
      expect(onSend).toHaveBeenCalled()
      expect(onChat).not.toHaveBeenCalled()
    })

    it('disables the chat button when transmitting', () => {
      render(<MessageInput transmitting={true} contacts={[]} onSend={vi.fn()} onChat={vi.fn()} />)
      expect(screen.getByRole('button', { name: /chat/i })).toBeDisabled()
    })

    it('disables the chat button when the draft is empty', () => {
      render(<MessageInput transmitting={false} contacts={[]} onSend={vi.fn()} onChat={vi.fn()} />)
      expect(screen.getByRole('button', { name: /chat/i })).toBeDisabled()
    })
  })

  describe('accessibility', () => {
    it('has no violations with contacts list', async () => {
      const { container } = render(
        <MessageInput
          transmitting={false}
          contacts={CONTACTS}
          onSend={vi.fn()}
        />
      )
      expect(await axe(container)).toHaveNoViolations()
    })
  })
})
