import React from 'react'
import { render as rtlRender, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import { createRef } from 'react'
import { Spectrogram, SpectrogramHandle } from '../Spectrogram'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

// ---------------------------------------------------------------------------
// Canvas mock
// ---------------------------------------------------------------------------

// jsdom doesn't implement canvas — provide a minimal stub.
const mockImageData = {
  data: new Uint8ClampedArray(256 * 128 * 4),
  width: 256,
  height: 128,
  colorSpace: 'srgb' as PredefinedColorSpace,
}

const mockCtx = {
  clearRect: vi.fn(),
  fillRect: vi.fn(),
  drawImage: vi.fn(),
  createImageData: vi.fn().mockReturnValue(mockImageData),
  putImageData: vi.fn(),
  getImageData: vi.fn().mockReturnValue(mockImageData),
  fillStyle: '',
  canvas: { width: 256, height: 128 },
}

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    mockCtx as unknown as CanvasRenderingContext2D
  )
  // Reset call counts between tests
  mockCtx.clearRect.mockClear()
  mockCtx.fillRect.mockClear()
  mockCtx.putImageData.mockClear()
  mockCtx.createImageData.mockClear()
  // Reset imageData buffer so scroll shift (copyWithin) has a real typed array to work on
  mockImageData.data = new Uint8ClampedArray(256 * 128 * 4)
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('Spectrogram — rendering', () => {
  it('renders a canvas element', () => {
    render(<Spectrogram colormap="viridis" timeWindowS={30} />)
    const canvas = screen.getByLabelText('Live audio spectrogram waterfall')
    expect(canvas.tagName).toBe('CANVAS')
  })

  it('canvas has correct intrinsic dimensions', () => {
    render(<Spectrogram colormap="viridis" timeWindowS={30} />)
    const canvas = screen.getByLabelText('Live audio spectrogram waterfall') as HTMLCanvasElement
    expect(canvas.width).toBe(256)
    expect(canvas.height).toBe(128)
  })

  it('fills canvas black on initial render', () => {
    render(<Spectrogram colormap="viridis" timeWindowS={30} />)
    expect(mockCtx.fillRect).toHaveBeenCalled()
  })

  it('renders with grayscale colormap without error', () => {
    expect(() =>
      render(<Spectrogram colormap="grayscale" timeWindowS={10} />)
    ).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Imperative handle — pushRow
// ---------------------------------------------------------------------------

describe('Spectrogram — imperative handle (pushRow)', () => {
  it('exposes pushRow via forwardRef', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={30} />)
    expect(ref.current).not.toBeNull()
    expect(typeof ref.current!.pushRow).toBe('function')
  })

  it('does not call putImageData until rowsPerPx rows have accumulated', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={30} />)
    mockCtx.putImageData.mockClear()

    // With timeWindowS=30 and CANVAS_HEIGHT=128, rowsPerPx = max(1, round(20*30/128)) = 5
    // Push 4 rows — should NOT flush yet
    for (let i = 0; i < 4; i++) {
      ref.current!.pushRow(new Array(32).fill(128))
    }
    expect(mockCtx.putImageData).not.toHaveBeenCalled()
  })

  it('calls putImageData after rowsPerPx rows accumulate', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={30} />)
    mockCtx.putImageData.mockClear()

    // rowsPerPx = 5 for timeWindowS=30
    for (let i = 0; i < 5; i++) {
      ref.current!.pushRow(new Array(256).fill(100))
    }
    expect(mockCtx.putImageData).toHaveBeenCalledTimes(1)
  })

  it('immediately flushes when timeWindowS is very small (rowsPerPx=1)', () => {
    // timeWindowS=1 → rowsPerPx = max(1, round(20*1/128)) = max(1,0) = 1
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    mockCtx.putImageData.mockClear()

    ref.current!.pushRow(new Array(256).fill(200))
    expect(mockCtx.putImageData).toHaveBeenCalledTimes(1)
  })

  it('pushRow with VAD=true does not throw', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    expect(() => ref.current!.pushRow(new Array(256).fill(100), true, false)).not.toThrow()
  })

  it('pushRow with squelch=true does not throw', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    expect(() => ref.current!.pushRow(new Array(256).fill(100), false, true)).not.toThrow()
  })

  it('handles empty row without throwing', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    expect(() => ref.current!.pushRow([])).not.toThrow()
  })

  it('handles row shorter than canvas width without throwing', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    expect(() => ref.current!.pushRow(new Array(10).fill(50))).not.toThrow()
  })

  it('writes pixel data after flush (putImageData called with imageData)', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    mockCtx.putImageData.mockClear()

    ref.current!.pushRow(new Array(256).fill(255))

    expect(mockCtx.putImageData).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.any(Uint8ClampedArray) }),
      0,
      0
    )
  })

  it('multiple flushes each call putImageData', () => {
    const ref = createRef<SpectrogramHandle>()
    render(<Spectrogram ref={ref} colormap="viridis" timeWindowS={1} />)
    mockCtx.putImageData.mockClear()

    ref.current!.pushRow(new Array(256).fill(128))
    ref.current!.pushRow(new Array(256).fill(64))

    expect(mockCtx.putImageData).toHaveBeenCalledTimes(2)
  })
})

// ---------------------------------------------------------------------------
// Colormap / timeWindowS changes — canvas clear
// ---------------------------------------------------------------------------

describe('Spectrogram — prop changes', () => {
  it('clears canvas when colormap changes', () => {
    const { rerender } = render(<Spectrogram colormap="viridis" timeWindowS={30} />)
    mockCtx.fillRect.mockClear()

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <Spectrogram colormap="grayscale" timeWindowS={30} />
      </ThemeProvider>
    )

    expect(mockCtx.fillRect).toHaveBeenCalled()
  })

  it('clears canvas when timeWindowS changes', () => {
    const { rerender } = render(<Spectrogram colormap="viridis" timeWindowS={30} />)
    mockCtx.fillRect.mockClear()

    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <Spectrogram colormap="viridis" timeWindowS={60} />
      </ThemeProvider>
    )

    expect(mockCtx.fillRect).toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// DisplayName
// ---------------------------------------------------------------------------

describe('Spectrogram — displayName', () => {
  it('has displayName set', () => {
    expect(Spectrogram.displayName).toBe('Spectrogram')
  })
})
