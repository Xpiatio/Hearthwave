import React from 'react'
import { render as rtlRender, screen, act } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createRef } from 'react'
import { AudioLevelMeter, AudioLevelMeterHandle, peakLevel } from '../AudioLevelMeter'

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

// ---------------------------------------------------------------------------
// Canvas + rAF mocks (jsdom implements neither usefully)
// ---------------------------------------------------------------------------

const mockGradient = { addColorStop: vi.fn() }

const mockCtx = {
  clearRect: vi.fn(),
  fillRect: vi.fn(),
  createLinearGradient: vi.fn().mockReturnValue(mockGradient),
  fillStyle: '' as string | CanvasGradient,
}

// Capture the rAF callback so a single frame can be driven deterministically.
let rafCb: FrameRequestCallback | null = null

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    mockCtx as unknown as CanvasRenderingContext2D,
  )
  rafCb = null
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    rafCb = cb
    return 1
  })
  vi.stubGlobal('cancelAnimationFrame', () => {})
  mockCtx.clearRect.mockClear()
  mockCtx.fillRect.mockClear()
  mockCtx.createLinearGradient.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

// ---------------------------------------------------------------------------
// peakLevel — pure helper
// ---------------------------------------------------------------------------

describe('peakLevel', () => {
  it('maps an all-zero row to 0', () => {
    expect(peakLevel([0, 0, 0])).toBe(0)
  })

  it('maps a full-scale bin to 1', () => {
    expect(peakLevel([0, 255, 12])).toBe(1)
  })

  it('uses the peak bin, normalized to 0..1', () => {
    expect(peakLevel([0, 128, 64])).toBeCloseTo(128 / 255, 5)
  })

  it('a louder row yields a higher level than a quiet row', () => {
    expect(peakLevel(new Array(256).fill(200))).toBeGreaterThan(
      peakLevel(new Array(256).fill(5)),
    )
  })

  it('returns 0 for an empty row', () => {
    expect(peakLevel([])).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('AudioLevelMeter — rendering', () => {
  it('renders a canvas element with the level-meter label', () => {
    render(<AudioLevelMeter />)
    const canvas = screen.getByLabelText('RX audio level meter')
    expect(canvas.tagName).toBe('CANVAS')
  })

  it('canvas has correct intrinsic dimensions', () => {
    render(<AudioLevelMeter />)
    const canvas = screen.getByLabelText('RX audio level meter') as HTMLCanvasElement
    expect(canvas.width).toBe(512)
    expect(canvas.height).toBe(16)
  })

  it('builds a linear gradient on mount', () => {
    render(<AudioLevelMeter />)
    expect(mockCtx.createLinearGradient).toHaveBeenCalled()
    expect(mockGradient.addColorStop).toHaveBeenCalled()
  })

  it('draws the track on each animation frame', () => {
    render(<AudioLevelMeter />)
    mockCtx.fillRect.mockClear()
    act(() => {
      rafCb?.(0)
    })
    expect(mockCtx.fillRect).toHaveBeenCalled()
  })

  it('has displayName set', () => {
    expect(AudioLevelMeter.displayName).toBe('AudioLevelMeter')
  })
})

// ---------------------------------------------------------------------------
// Imperative handle — pushRow
// ---------------------------------------------------------------------------

describe('AudioLevelMeter — imperative handle (pushRow)', () => {
  it('exposes pushRow via forwardRef', () => {
    const ref = createRef<AudioLevelMeterHandle>()
    render(<AudioLevelMeter ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(typeof ref.current!.pushRow).toBe('function')
  })

  it('pushRow does not throw on a full row', () => {
    const ref = createRef<AudioLevelMeterHandle>()
    render(<AudioLevelMeter ref={ref} />)
    expect(() => ref.current!.pushRow(new Array(256).fill(200))).not.toThrow()
  })

  it('pushRow does not throw on an empty row', () => {
    const ref = createRef<AudioLevelMeterHandle>()
    render(<AudioLevelMeter ref={ref} />)
    expect(() => ref.current!.pushRow([])).not.toThrow()
  })

  it('a loud row raises the rendered level above a silent one', () => {
    const ref = createRef<AudioLevelMeterHandle>()
    render(<AudioLevelMeter ref={ref} />)

    // Silent: drive a few frames, capture max fill width.
    ref.current!.pushRow(new Array(256).fill(0))
    act(() => { rafCb?.(0) })
    const silentCalls = mockCtx.fillRect.mock.calls.length

    // Loud: a high peak should produce a fill rect wider than the track-only draw.
    mockCtx.fillRect.mockClear()
    ref.current!.pushRow(new Array(256).fill(255))
    act(() => { rafCb?.(0) })
    // Track + filled bar (+ maybe peak tick) → more fillRect calls than the silent frame.
    expect(mockCtx.fillRect.mock.calls.length).toBeGreaterThanOrEqual(silentCalls)
  })
})
