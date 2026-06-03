import { render as rtlRender, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { PluginSlot } from '../PluginSlot'
import type { PluginDefinition, PluginProps } from '../../../plugins'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

const BASE_PROPS: PluginProps = {
  send: vi.fn(),
  lastMessage: null,
  contacts: [],
  channelClear: true,
  transmitting: false,
}

function makePlugin(Component: React.ComponentType<PluginProps>): PluginDefinition {
  return { id: 'test-plugin', label: 'Test Plugin', component: Component }
}

describe('PluginSlot', () => {
  it('renders the plugin component', () => {
    const TestComponent = () => <div>Plugin Output</div>
    const plugin = makePlugin(TestComponent)
    render(<PluginSlot plugin={plugin} {...BASE_PROPS} />)
    expect(screen.getByText('Plugin Output')).toBeInTheDocument()
  })

  it('passes all PluginProps to the component', () => {
    const receivedProps: Partial<PluginProps> = {}
    const SpyComponent = (props: PluginProps) => {
      Object.assign(receivedProps, props)
      return <div>spy</div>
    }
    const plugin = makePlugin(SpyComponent)
    const sendFn = vi.fn()
    render(
      <PluginSlot
        plugin={plugin}
        send={sendFn}
        lastMessage={null}
        contacts={[]}
        channelClear={false}
        transmitting={true}
      />
    )
    expect(receivedProps.send).toBe(sendFn)
    expect(receivedProps.lastMessage).toBeNull()
    expect(receivedProps.contacts).toEqual([])
    expect(receivedProps.channelClear).toBe(false)
    expect(receivedProps.transmitting).toBe(true)
  })

  it('passes contacts array to the component', () => {
    const contacts = [{ callsign: 'W1AAA', name: 'Alice' }]
    let capturedContacts: typeof contacts = []
    const ContactsComponent = (props: PluginProps) => {
      capturedContacts = props.contacts as typeof contacts
      return <div>contacts-test</div>
    }
    const plugin = makePlugin(ContactsComponent)
    render(<PluginSlot plugin={plugin} {...BASE_PROPS} contacts={contacts} />)
    expect(capturedContacts).toEqual(contacts)
  })

  it('passes lastMessage when provided', () => {
    let capturedMsg: PluginProps['lastMessage'] = null
    const MsgComponent = (props: PluginProps) => {
      capturedMsg = props.lastMessage
      return <div>msg-test</div>
    }
    const plugin = makePlugin(MsgComponent)
    const lastMessage = { type: 'status' as const, radio_connected: true, volume_ok: true, channel_clear: true }
    render(<PluginSlot plugin={plugin} {...BASE_PROPS} lastMessage={lastMessage} />)
    expect(capturedMsg).toEqual(lastMessage)
  })

  it('calls the plugin.component (not a wrong component)', () => {
    const ComponentA = () => <div>Component A</div>
    const ComponentB = () => <div>Component B</div>
    const pluginA = makePlugin(ComponentA)
    render(<PluginSlot plugin={pluginA} {...BASE_PROPS} />)
    expect(screen.getByText('Component A')).toBeInTheDocument()
    expect(screen.queryByText('Component B')).not.toBeInTheDocument()
  })
})
