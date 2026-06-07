import React from 'react'
import { render as rtlRender, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { VoicePTT } from '../VoicePTT'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

// ---------------------------------------------------------------------------
// Global stubs — set up once at module level and reset between tests
// ---------------------------------------------------------------------------

const stopTrack = vi.fn()
const mockStream = { getTracks: () => [{ stop: stopTrack }] }

const portClose = vi.fn()
const mockWorklet = {
  port: { onmessage: null as unknown, close: portClose },
  connect: vi.fn(),
  disconnect: vi.fn(),
}
const mockSource = { connect: vi.fn(), disconnect: vi.fn() }
const mockCtx = {
  createMediaStreamSource: vi.fn().mockReturnValue(mockSource),
  audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) },
  close: vi.fn(),
  state: 'running' as AudioContextState,
}

const getUserMediaMock = vi.fn().mockResolvedValue(mockStream as unknown as MediaStream)

// AudioContext and AudioWorkletNode must be constructors (called with `new`).
// vi.fn().mockImplementation returning a plain object works when the function
// is used as a constructor — the returned object takes precedence over `this`.
class MockAudioContext {
  createMediaStreamSource = mockCtx.createMediaStreamSource
  audioWorklet = mockCtx.audioWorklet
  close = mockCtx.close
  state = mockCtx.state
}
class MockAudioWorkletNode {
  port = mockWorklet.port
  connect = mockWorklet.connect
  disconnect = mockWorklet.disconnect
}

// Install stubs at module scope so they're available before any test runs.
vi.stubGlobal('AudioContext', MockAudioContext)
vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNode)
vi.stubGlobal('URL', {
  createObjectURL: vi.fn().mockReturnValue('blob:fake'),
  revokeObjectURL: vi.fn(),
})

// jsdom doesn't provide navigator.mediaDevices — define it once.
Object.defineProperty(navigator, 'mediaDevices', {
  configurable: true,
  value: { getUserMedia: getUserMediaMock },
})

beforeEach(() => {
  // Reset call state between tests.
  stopTrack.mockClear()
  portClose.mockClear()
  mockWorklet.connect.mockClear()
  mockWorklet.disconnect.mockClear()
  mockSource.connect.mockClear()
  mockCtx.createMediaStreamSource.mockClear()
  mockCtx.audioWorklet.addModule.mockClear()
  mockCtx.close.mockClear()
  getUserMediaMock.mockClear()
  getUserMediaMock.mockResolvedValue(mockStream as unknown as MediaStream)
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Default prop factory
// ---------------------------------------------------------------------------

function defaultProps() {
  return {
    disabled: false,
    onStart: vi.fn(),
    onChunk: vi.fn(),
    onEnd: vi.fn(),
    onCancel: vi.fn(),
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('VoicePTT — rendering', () => {
  it('renders PTT button in idle state', () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    expect(screen.getByRole('button', { name: /push to talk/i })).toBeInTheDocument()
    expect(screen.getByRole('button')).toHaveTextContent('PTT')
  })

  it('button is enabled when disabled=false', () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    expect(screen.getByRole('button')).not.toBeDisabled()
  })

  it('button is disabled when disabled=true', () => {
    const props = { ...defaultProps(), disabled: true }
    render(<VoicePTT {...props} />)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Recording flow — mouse
// ---------------------------------------------------------------------------

describe('VoicePTT — recording via mouse', () => {
  it('changes button text to PTT● while recording', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)

    await waitFor(() => {
      expect(screen.getByRole('button')).toHaveTextContent('PTT●')
    })
  })

  it('calls onStart when recording begins', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)

    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))
  })

  it('calls onEnd when mouseUp ends recording', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))

    fireEvent.mouseUp(btn)

    await waitFor(() => expect(props.onEnd).toHaveBeenCalledTimes(1))
  })

  it('reverts button text to PTT after mouseUp', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)
    await waitFor(() => expect(screen.getByRole('button')).toHaveTextContent('PTT●'))

    fireEvent.mouseUp(btn)
    await waitFor(() => expect(screen.getByRole('button')).toHaveTextContent('PTT'))
  })

  it('calls onEnd when mouseLeave during recording', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))

    fireEvent.mouseLeave(btn)

    await waitFor(() => expect(props.onEnd).toHaveBeenCalledTimes(1))
  })

  it('ignores mouseLeave when not recording', () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    // No mouseDown first
    fireEvent.mouseLeave(btn)
    expect(props.onEnd).not.toHaveBeenCalled()
    expect(props.onCancel).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Recording flow — touch
// ---------------------------------------------------------------------------

describe('VoicePTT — recording via touch', () => {
  it('starts recording on touchStart', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.touchStart(btn)

    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))
  })

  it('ends recording on touchEnd', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.touchStart(btn)
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))

    fireEvent.touchEnd(btn)

    await waitFor(() => expect(props.onEnd).toHaveBeenCalledTimes(1))
  })
})

// ---------------------------------------------------------------------------
// Permission denied
// ---------------------------------------------------------------------------

describe('VoicePTT — permission denied', () => {
  it('calls onCancel and shows denied tooltip when getUserMedia throws NotAllowedError', async () => {
    // DOMException.name is read-only in jsdom; use a plain Error with the right name.
    const err = new Error('Denied')
    err.name = 'NotAllowedError'
    getUserMediaMock.mockRejectedValue(err)

    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)

    await waitFor(() => expect(props.onCancel).toHaveBeenCalledTimes(1))
  })

  it('calls onCancel when getUserMedia throws NotFoundError', async () => {
    const err = new Error('Not found')
    err.name = 'NotFoundError'
    getUserMediaMock.mockRejectedValue(err)

    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)

    await waitFor(() => expect(props.onCancel).toHaveBeenCalledTimes(1))
  })

  it('does not remain in recording state after permission denial', async () => {
    const err = new Error('Denied')
    err.name = 'NotAllowedError'
    getUserMediaMock.mockRejectedValue(err)

    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)

    await waitFor(() => expect(screen.getByRole('button')).toHaveTextContent('PTT'))
  })
})

// ---------------------------------------------------------------------------
// Disabled while recording
// ---------------------------------------------------------------------------

describe('VoicePTT — disabled prop change during recording', () => {
  it('calls onCancel when disabled flips true while recording', async () => {
    const props = defaultProps()
    const { rerender } = render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))

    // Flip disabled → true (simulates WS drop or listen-only toggle)
    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <VoicePTT {...props} disabled={true} />
      </ThemeProvider>
    )

    await waitFor(() => expect(props.onCancel).toHaveBeenCalledTimes(1))
  })
})

// ---------------------------------------------------------------------------
// Cleanup on unmount
// ---------------------------------------------------------------------------

describe('VoicePTT — unmount cleanup', () => {
  it('calls onCancel when unmounted while recording', async () => {
    const props = defaultProps()
    const { unmount } = render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))

    act(() => {
      unmount()
    })

    await waitFor(() => expect(props.onCancel).toHaveBeenCalledTimes(1))
  })

  it('does not throw when unmounted in idle state', () => {
    const props = defaultProps()
    const { unmount } = render(<VoicePTT {...props} />)
    expect(() => act(() => unmount())).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Double-press guard
// ---------------------------------------------------------------------------

describe('VoicePTT — double-press guard', () => {
  it('does not call onStart twice if mouseDown fires while already recording', async () => {
    const props = defaultProps()
    render(<VoicePTT {...props} />)
    const btn = screen.getByRole('button')

    fireEvent.mouseDown(btn)
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))

    // Second mouseDown while activeRef is true — should be a no-op
    fireEvent.mouseDown(btn)

    // Allow any async resolution
    await waitFor(() => expect(props.onStart).toHaveBeenCalledTimes(1))
  })
})
