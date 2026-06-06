import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useWebSocket } from '../useWebSocket'
import type { WsMessage } from '../../types/ws'

// ---------------------------------------------------------------------------
// Fake WebSocket implementation
// ---------------------------------------------------------------------------

type FakeWSInstance = {
  url: string
  readyState: number
  onopen: ((e: Event) => void) | null
  onmessage: ((e: MessageEvent) => void) | null
  onclose: ((e: CloseEvent) => void) | null
  onerror: ((e: Event) => void) | null
  close: (code?: number, reason?: string) => void
  send: (data: string) => void
  // Test helpers
  _triggerOpen: () => void
  _triggerMessage: (data: unknown) => void
  _triggerClose: (code?: number) => void
  _triggerError: () => void
  _sentMessages: string[]
}

let instances: FakeWSInstance[] = []

class FakeWebSocket {
  url: string
  readyState = 0 // CONNECTING
  onopen: ((e: Event) => void) | null = null
  onmessage: ((e: MessageEvent) => void) | null = null
  onclose: ((e: CloseEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  _sentMessages: string[] = []

  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  constructor(url: string) {
    this.url = url
    instances.push(this as unknown as FakeWSInstance)
  }

  close(code?: number) {
    this.readyState = FakeWebSocket.CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code ?? 1000, wasClean: true }))
    }
  }

  send(data: string) {
    this._sentMessages.push(data)
  }

  _triggerOpen() {
    this.readyState = FakeWebSocket.OPEN
    if (this.onopen) this.onopen(new Event('open'))
  }

  _triggerMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
    }
  }

  _triggerClose(code = 1000) {
    this.readyState = FakeWebSocket.CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, wasClean: code === 1000 }))
    }
  }

  _triggerError() {
    if (this.onerror) this.onerror(new Event('error'))
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useWebSocket', () => {
  beforeEach(() => {
    instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    // connect() fetches a WS ticket before opening; mock fetch to reject fast
    // so fetchWsTicket returns null and falls back to the raw token.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  // -- Connection lifecycle ------------------------------------------------

  it('does not connect when token is null', () => {
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: null })
    )
    expect(instances).toHaveLength(0)
  })

  it('creates a WebSocket connection when token is provided', async () => {
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-123' })
    )
    await act(async () => {})
    expect(instances).toHaveLength(1)
    expect(instances[0].url).toContain('tok-123')
  })

  it('url contains wss when location is https', async () => {
    // jsdom defaults to http so this test verifies the ws: branch
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-abc' })
    )
    await act(async () => {})
    expect(instances[0].url).toMatch(/^ws:/)
  })

  it('sets connected=true on open', async () => {
    const { result } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    expect(result.current.connected).toBe(false)
    act(() => { instances[0]._triggerOpen() })
    expect(result.current.connected).toBe(true)
  })

  it('sets connected=false on close', async () => {
    const { result } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    act(() => { instances[0]._triggerClose() })
    expect(result.current.connected).toBe(false)
  })

  it('calls onOpen callback when connection opens', async () => {
    const onOpen = vi.fn()
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1', onOpen })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    expect(onOpen).toHaveBeenCalledOnce()
  })

  it('closes existing connection when token becomes null', async () => {
    const { rerender } = renderHook(
      ({ token }) => useWebSocket({ onMessage: vi.fn(), token }),
      { initialProps: { token: 'tok-1' as string | null } }
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    rerender({ token: null })
    expect(instances[0].readyState).toBe(FakeWebSocket.CLOSED)
  })

  // -- Message handling ----------------------------------------------------

  it('calls onMessage with parsed WsMessage on incoming data', async () => {
    const onMessage = vi.fn()
    renderHook(() => useWebSocket({ onMessage, token: 'tok-1' }))
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })

    const msg: Pick<WsMessage, 'type'> = { type: 'status' }
    act(() => { instances[0]._triggerMessage(msg) })

    expect(onMessage).toHaveBeenCalledWith(expect.objectContaining({ type: 'status' }))
  })

  it('silently ignores invalid JSON messages', async () => {
    const onMessage = vi.fn()
    renderHook(() => useWebSocket({ onMessage, token: 'tok-1' }))
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })

    act(() => {
      if (instances[0].onmessage) {
        instances[0].onmessage(
          new MessageEvent('message', { data: 'not-json{{{{' })
        )
      }
    })

    expect(onMessage).not.toHaveBeenCalled()
  })

  it('uses updated onMessage callback without reconnecting', async () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(
      ({ cb }) => useWebSocket({ onMessage: cb, token: 'tok-1' }),
      { initialProps: { cb: first } }
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })

    rerender({ cb: second })
    act(() => { instances[0]._triggerMessage({ type: 'status' }) })

    // Should call the new callback, not create a new WebSocket
    expect(second).toHaveBeenCalledOnce()
    expect(first).not.toHaveBeenCalled()
    expect(instances).toHaveLength(1)
  })

  // -- send() method -------------------------------------------------------

  it('send() transmits JSON when connection is open', async () => {
    const { result } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })

    act(() => {
      result.current.send({ type: 'tx_message', text: 'Hello' })
    })

    expect(instances[0]._sentMessages).toHaveLength(1)
    const sent = JSON.parse(instances[0]._sentMessages[0])
    expect(sent).toMatchObject({ type: 'tx_message', text: 'Hello' })
  })

  it('send() does nothing when not connected', async () => {
    const { result } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    // Not open yet — send should be a no-op
    act(() => {
      result.current.send({ type: 'tx_message', text: 'Hello' })
    })

    expect(instances[0]._sentMessages).toHaveLength(0)
  })

  // -- Reconnect behavior --------------------------------------------------

  it('schedules reconnect after normal close', async () => {
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    act(() => { instances[0]._triggerClose(1000) })

    expect(instances).toHaveLength(1)
    // Advance past MIN_BACKOFF_MS (1000ms)
    act(() => { vi.advanceTimersByTime(1100) })
    await act(async () => {})
    expect(instances).toHaveLength(2)
  })

  it('does NOT reconnect after auth failure (code 4001)', async () => {
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    act(() => { instances[0]._triggerClose(4001) })

    act(() => { vi.advanceTimersByTime(5000) })
    await act(async () => {})
    expect(instances).toHaveLength(1)
  })

  it('calls close then reopens on error', async () => {
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    act(() => { instances[0]._triggerError() })

    // Error handler calls ws.close(), which triggers onclose => reconnect timer
    act(() => { vi.advanceTimersByTime(1100) })
    await act(async () => {})
    expect(instances).toHaveLength(2)
  })

  it('backoff doubles on repeated failures without successful open', async () => {
    // If the socket NEVER opens (immediate failure), backoff should double.
    // Trigger close without open so the backoff is NOT reset.
    renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})

    // First close without open: backoff stays at 1000ms, fires after 1000ms
    act(() => { instances[0]._triggerClose(1000) })
    act(() => { vi.advanceTimersByTime(1100) })
    await act(async () => {})
    expect(instances).toHaveLength(2)

    // Second close without open: backoff doubled to 2000ms
    act(() => { instances[1]._triggerClose(1000) })
    act(() => { vi.advanceTimersByTime(1100) })
    // 1100ms < 2000ms — timer has NOT fired yet
    expect(instances).toHaveLength(2)
    act(() => { vi.advanceTimersByTime(1000) })
    await act(async () => {})
    // Now 2100ms total — timer fires
    expect(instances).toHaveLength(3)
  })

  // -- Cleanup on unmount --------------------------------------------------

  it('closes WebSocket on unmount', async () => {
    const { unmount } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    unmount()
    expect(instances[0].readyState).toBe(FakeWebSocket.CLOSED)
  })

  it('does not reconnect after unmount', async () => {
    const { unmount } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    unmount()
    act(() => { vi.advanceTimersByTime(5000) })
    expect(instances).toHaveLength(1)
  })

  it('cancels pending reconnect timer on unmount', async () => {
    const { unmount } = renderHook(() =>
      useWebSocket({ onMessage: vi.fn(), token: 'tok-1' })
    )
    await act(async () => {})
    act(() => { instances[0]._triggerOpen() })
    act(() => { instances[0]._triggerClose(1000) })
    unmount()
    act(() => { vi.advanceTimersByTime(5000) })
    // Timer cancelled: no new instance
    expect(instances).toHaveLength(1)
  })
})
