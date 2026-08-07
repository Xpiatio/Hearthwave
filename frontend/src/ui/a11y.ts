/** Shared accessibility primitives.
 *
 *  `display: none` and `visibility: hidden` take content away from screen
 *  readers too. This takes it away only from the eye, for text that is
 *  redundant when you can see the layout but essential when you can't —
 *  a spelled-out compass point, or a pointer to the view that carries the
 *  same data as a map.
 */
export const visuallyHidden = {
  position: 'absolute',
  width: 1,
  height: 1,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
} as const;
