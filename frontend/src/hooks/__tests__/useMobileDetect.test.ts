import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useMobileDetect } from '../useMobileDetect'

vi.mock('../useDeviceClass', () => ({
  useDeviceClass: vi.fn(),
}))

import { useDeviceClass } from '../useDeviceClass'

describe('useMobileDetect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Note: semantics intentionally tightened — phone now requires BOTH coarse pointer AND narrow width (AND), where the old hook used OR.
  it('returns true when useDeviceClass returns "phone"', () => {
    vi.mocked(useDeviceClass).mockReturnValue('phone')
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(true)
  })

  it('returns false when useDeviceClass returns "tablet"', () => {
    vi.mocked(useDeviceClass).mockReturnValue('tablet')
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(false)
  })

  it('returns false when useDeviceClass returns "desktop"', () => {
    vi.mocked(useDeviceClass).mockReturnValue('desktop')
    const { result } = renderHook(() => useMobileDetect())
    expect(result.current).toBe(false)
  })

  it('returns a stable boolean — same value on re-render', () => {
    vi.mocked(useDeviceClass).mockReturnValue('phone')
    const { result, rerender } = renderHook(() => useMobileDetect())
    const first = result.current
    rerender()
    expect(result.current).toBe(first)
  })
})
