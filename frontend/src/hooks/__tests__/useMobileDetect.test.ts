import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useMobileDetect } from '../useMobileDetect'

function mockMatchMedia(pointer: boolean, maxWidth: boolean) {
  return vi.fn().mockImplementation((query: string) => ({
    matches:
      query === '(pointer: coarse)' ? pointer :
      query === '(max-width: 600px)' ? maxWidth :
      false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

describe('useMobileDetect', () => {
  const originalMatchMedia = window.matchMedia

  afterEach(() => {
    Object.defineProperty(window, 'matchMedia', { value: originalMatchMedia, writable: true })
  })

  it('returns true when pointer:coarse matches (touch device)', () => {
    Object.defineProperty(window, 'matchMedia', {
      value: mockMatchMedia(true, false),
      writable: true,
    })
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(true)
  })

  it('returns true when max-width:600px matches (narrow viewport fallback)', () => {
    Object.defineProperty(window, 'matchMedia', {
      value: mockMatchMedia(false, true),
      writable: true,
    })
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(true)
  })

  it('returns true when both pointer:coarse and max-width:600px match', () => {
    Object.defineProperty(window, 'matchMedia', {
      value: mockMatchMedia(true, true),
      writable: true,
    })
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(true)
  })

  it('returns false when neither query matches (desktop)', () => {
    Object.defineProperty(window, 'matchMedia', {
      value: mockMatchMedia(false, false),
      writable: true,
    })
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(false)
  })

  it('returns a stable boolean — same value on re-render', () => {
    Object.defineProperty(window, 'matchMedia', {
      value: mockMatchMedia(true, false),
      writable: true,
    })
    const { result, rerender } = renderHook(() => useMobileDetect())
    const first = result.current
    rerender()
    expect(result.current).toBe(first)
  })
})
