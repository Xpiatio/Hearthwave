import { renderHook } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useDeviceClass } from '../useDeviceClass';

type Listener = (e: MediaQueryListEvent) => void;

/** Install a matchMedia mock where `trueQueries` match. Returns a fire() to flip state. */
function installMatchMedia(matchFor: (q: string) => boolean) {
  const listeners: Listener[] = [];
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: matchFor(query),
    media: query,
    addEventListener: (_: string, cb: Listener) => listeners.push(cb),
    removeEventListener: (_: string, cb: Listener) => {
      const i = listeners.indexOf(cb); if (i >= 0) listeners.splice(i, 1);
    },
    addListener: (cb: Listener) => listeners.push(cb),
    removeListener: () => {},
    dispatchEvent: () => true,
  })) as unknown as typeof window.matchMedia;
  return listeners;
}

describe('useDeviceClass', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('returns "phone" for coarse pointer at narrow width', () => {
    installMatchMedia((q) => q.includes('pointer: coarse') && q.includes('max-width: 600px') && !q.includes('min-width'));
    const { result } = renderHook(() => useDeviceClass());
    expect(result.current).toBe('phone');
  });

  it('returns "tablet" for coarse pointer in the mid width band', () => {
    installMatchMedia((q) =>
      (q.includes('pointer: coarse') && q.includes('min-width: 601px') && q.includes('max-width: 1200px')));
    const { result } = renderHook(() => useDeviceClass());
    expect(result.current).toBe('tablet');
  });

  it('returns "desktop" for a fine pointer', () => {
    installMatchMedia(() => false);
    const { result } = renderHook(() => useDeviceClass());
    expect(result.current).toBe('desktop');
  });
});
