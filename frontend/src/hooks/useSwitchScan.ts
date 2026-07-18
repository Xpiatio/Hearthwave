import { useEffect, type RefObject } from 'react';

/**
 * Single-switch auto-scan: while enabled, moves real DOM focus through the
 * container's `[data-scan="true"]` elements on a timer, in DOM order,
 * wrapping at the end. The user's switch activates the focused element
 * natively (Enter/Space on a button), so no click plumbing is needed and
 * the highlight is the theme's global focus-visible ring. Disabled elements
 * are skipped. The element list is re-queried every tick so dynamic grids
 * (AAC categories, operator-tier cards) stay correct.
 */
export function useSwitchScan(
  enabled: boolean,
  intervalMs: number,
  containerRef: RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    if (!enabled) return;
    let idx = -1;
    const timer = setInterval(() => {
      const root = containerRef.current;
      if (!root) return;
      const els = Array.from(root.querySelectorAll<HTMLElement>('[data-scan="true"]')).filter(
        (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-disabled') !== 'true',
      );
      if (els.length === 0) return;
      idx = (idx + 1) % els.length;
      els[idx].focus();
    }, intervalMs);
    return () => clearInterval(timer);
  }, [enabled, intervalMs, containerRef]);
}
