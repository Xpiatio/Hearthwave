import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useEscapeToHome } from '../useEscapeToHome'

function fireEscape(defaultPrevented = false) {
  const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
  if (defaultPrevented) event.preventDefault()
  document.dispatchEvent(event)
}

describe('useEscapeToHome', () => {
  it('fires onGoHome when Escape is pressed', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    fireEscape()
    expect(onGoHome).toHaveBeenCalledTimes(1)
  })

  it('ignores keys other than Escape', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    expect(onGoHome).not.toHaveBeenCalled()
  })

  it('ignores Escape when defaultPrevented', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    fireEscape(true)
    expect(onGoHome).not.toHaveBeenCalled()
  })

  it('is a no-op when onGoHome is undefined', () => {
    expect(() => {
      renderHook(() => useEscapeToHome(undefined))
      fireEscape()
    }).not.toThrow()
  })

  it('removes its listener on unmount', () => {
    const onGoHome = vi.fn()
    const { unmount } = renderHook(() => useEscapeToHome(onGoHome))
    unmount()
    fireEscape()
    expect(onGoHome).not.toHaveBeenCalled()
  })
})
