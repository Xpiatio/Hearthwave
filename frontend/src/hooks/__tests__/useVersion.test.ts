import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useVersion } from '../useVersion'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useVersion', () => {
  it('returns the version from /health', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)

    const { result } = renderHook(() => useVersion())
    await waitFor(() => expect(result.current).toBe('2.5.2'))
    expect(global.fetch).toHaveBeenCalledWith('/health')
  })

  it('stays null when the request fails', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useVersion())
    // Give the rejected promise a tick to settle.
    await new Promise((r) => setTimeout(r, 0))
    expect(result.current).toBeNull()
  })
})
