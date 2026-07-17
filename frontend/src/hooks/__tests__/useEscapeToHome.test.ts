import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useEscapeToHome } from '../useEscapeToHome'

function fireEscape(defaultPrevented = false) {
  const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
  if (defaultPrevented) event.preventDefault()
  document.dispatchEvent(event)
}

function fireEscapeOn(target: HTMLElement) {
  const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true, bubbles: true })
  target.dispatchEvent(event)
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

  it('does not fire when Escape is pressed inside a text input (draft guard)', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    const input = document.createElement('input')
    input.type = 'text'
    document.body.appendChild(input)
    input.focus()
    fireEscapeOn(input)
    expect(onGoHome).not.toHaveBeenCalled()
    input.remove()
  })

  it('does not fire when Escape is pressed inside a textarea (draft guard)', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    const textarea = document.createElement('textarea')
    document.body.appendChild(textarea)
    textarea.focus()
    fireEscapeOn(textarea)
    expect(onGoHome).not.toHaveBeenCalled()
    textarea.remove()
  })

  it('does not fire when Escape is pressed inside a contenteditable element', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    // jsdom doesn't reflect the `contentEditable` IDL property to the
    // attribute (or implement `isContentEditable`), so set the attribute
    // directly — this is how React renders `contentEditable` anyway.
    const div = document.createElement('div')
    div.setAttribute('contenteditable', 'true')
    document.body.appendChild(div)
    div.focus()
    fireEscapeOn(div)
    expect(onGoHome).not.toHaveBeenCalled()
    div.remove()
  })

  it('still fires when Escape is pressed while a non-text element is focused', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    const button = document.createElement('button')
    document.body.appendChild(button)
    button.focus()
    fireEscapeOn(button)
    expect(onGoHome).toHaveBeenCalledTimes(1)
    button.remove()
  })

  it('still fires when Escape is pressed on a non-text input type (e.g. checkbox)', () => {
    const onGoHome = vi.fn()
    renderHook(() => useEscapeToHome(onGoHome))
    const input = document.createElement('input')
    input.type = 'checkbox'
    document.body.appendChild(input)
    input.focus()
    fireEscapeOn(input)
    expect(onGoHome).toHaveBeenCalledTimes(1)
    input.remove()
  })
})
