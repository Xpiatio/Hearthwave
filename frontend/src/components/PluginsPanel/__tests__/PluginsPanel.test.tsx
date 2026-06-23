import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { PluginsPanel, type PluginDraft } from '../PluginsPanel'
import type { PluginManifest } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

function manifest(over: Partial<PluginManifest> = {}): PluginManifest {
  return {
    id: 'meshcore', name: 'MeshCore', description: 'MeshCore bridge', version: '1.0.0',
    enabled: false, conflicts_with: [], config_schema: [], config: {}, tx_composition: null,
    ...over,
  }
}

const MESHCORE = manifest({ id: 'meshcore', name: 'MeshCore', conflicts_with: ['meshtastic'] })
const MESHTASTIC = manifest({ id: 'meshtastic', name: 'Meshtastic', conflicts_with: ['meshcore'] })
const NCS = manifest({ id: 'ncs', name: 'Net Control Station', enabled: true, conflicts_with: [] })
const PLUGINS = [MESHCORE, MESHTASTIC, NCS]

function draft(over: PluginDraft = {}): PluginDraft {
  return {
    meshcore: { enabled: false }, meshtastic: { enabled: false }, ncs: { enabled: true }, ...over,
  }
}

describe('PluginsPanel', () => {
  it('renders a row per installed plugin', () => {
    render(<PluginsPanel plugins={PLUGINS} value={draft()} onChange={vi.fn()} />)
    expect(screen.getByText('MeshCore')).toBeInTheDocument()
    expect(screen.getByText('Meshtastic')).toBeInTheDocument()
    expect(screen.getByText('Net Control Station')).toBeInTheDocument()
  })

  it('reflects enabled state from the draft', () => {
    render(<PluginsPanel plugins={PLUGINS} value={draft({ meshcore: { enabled: true } })} onChange={vi.fn()} />)
    const switches = screen.getAllByRole('switch')
    expect(switches[0]).toBeChecked()    // meshcore
    expect(switches[1]).not.toBeChecked() // meshtastic
  })

  it('enabling a plugin disables the one it conflicts with', () => {
    const onChange = vi.fn()
    render(<PluginsPanel plugins={PLUGINS} value={draft({ meshcore: { enabled: true } })} onChange={onChange} />)
    fireEvent.click(screen.getAllByRole('switch')[1]) // turn meshtastic on
    const next = onChange.mock.calls[0][0] as PluginDraft
    expect(next.meshtastic.enabled).toBe(true)
    expect(next.meshcore.enabled).toBe(false)
  })

  it('disabling a plugin does not touch its conflicts', () => {
    const onChange = vi.fn()
    render(<PluginsPanel plugins={PLUGINS} value={draft({ meshcore: { enabled: true } })} onChange={onChange} />)
    fireEvent.click(screen.getAllByRole('switch')[0]) // turn meshcore off
    const next = onChange.mock.calls[0][0] as PluginDraft
    expect(next.meshcore.enabled).toBe(false)
    expect(next.meshtastic.enabled).toBe(false)
  })

  it('renders the config form for an enabled plugin', () => {
    const withField = manifest({
      id: 'meshcore', name: 'MeshCore', enabled: true,
      config_schema: [{ key: 'serial_port', label: 'Device', type: 'text', default: '/dev/ttyUSB0', help: '', options: [], minimum: null, maximum: null }],
      config: { serial_port: '/dev/ttyUSB0' },
    })
    render(<PluginsPanel plugins={[withField]} value={{ meshcore: { enabled: true, serial_port: '/dev/ttyUSB0' } }} onChange={vi.fn()} />)
    expect(screen.getByLabelText('Device')).toBeInTheDocument()
  })

  it('shows a load error and no toggle for a failed plugin', () => {
    const broken = manifest({ id: 'broken', name: 'broken', error: 'ImportError: boom' })
    render(<PluginsPanel plugins={[broken]} value={{}} onChange={vi.fn()} />)
    expect(screen.getByText(/Failed to load: ImportError: boom/)).toBeInTheDocument()
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })

  it('shows a conflict note', () => {
    render(<PluginsPanel plugins={PLUGINS} value={draft()} onChange={vi.fn()} />)
    expect(screen.getAllByText(/Enabling this disables:/).length).toBeGreaterThan(0)
  })

  it('offers install / reload / uninstall actions when handlers are provided', () => {
    const onInstallFile = vi.fn(); const onReload = vi.fn(); const onUninstall = vi.fn()
    render(<PluginsPanel plugins={[NCS]} value={draft()} onChange={vi.fn()}
                         onInstallFile={onInstallFile} onReload={onReload} onUninstall={onUninstall} />)
    expect(screen.getByRole('button', { name: /install plugin/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /reload/i }))
    expect(onReload).toHaveBeenCalledWith('ncs')
    fireEvent.click(screen.getByRole('button', { name: /uninstall/i }))
    expect(onUninstall).toHaveBeenCalledWith('ncs')
  })
})
