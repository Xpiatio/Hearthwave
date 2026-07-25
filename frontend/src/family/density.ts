/** Roster density: how tightly the family board packs member cards.
 *
 *  A household of three wants big, glanceable cards; a household of twelve
 *  wants to see everyone at once. Rather than one fixed card size, the board
 *  picks a tier from the member count, and both the grid's column bounds and
 *  the card's internals scale with it.
 *
 *  Sizes stay in theme spacing units and typography variants rather than raw
 *  pixels, so they still track the user's fontScale — a compact tier packs
 *  more in, it does not opt out of the accessibility scaling. The one raw-px
 *  values are the grid column bounds, which have to be pixels to feed
 *  `minmax()`.
 */

export type Density = 'roomy' | 'medium' | 'compact';

export interface DensitySpec {
  /** Grid column bounds, px — feed `minmax()` in the roster grid. */
  minColumnPx: number;
  maxColumnPx: number;
  /** Avatar emoji size. Decorative and aria-hidden, so safe to shrink. */
  emojiFontSize: string;
  /** Typography variant for the member's name. */
  nameVariant: 'subtitle1' | 'subtitle2' | 'body2';
  /** Typography variant for the "Last heard …" line. */
  detailVariant: 'body2' | 'caption';
  /** Card padding and internal gap, in theme spacing units. */
  padding: number;
  gap: number;
}

const SPECS: Record<Density, DensitySpec> = {
  roomy: {
    minColumnPx: 260, maxColumnPx: 380,
    emojiFontSize: '2.5rem', nameVariant: 'subtitle1', detailVariant: 'body2',
    padding: 2, gap: 1,
  },
  medium: {
    minColumnPx: 200, maxColumnPx: 280,
    emojiFontSize: '2rem', nameVariant: 'subtitle2', detailVariant: 'body2',
    padding: 1.5, gap: 0.75,
  },
  compact: {
    minColumnPx: 150, maxColumnPx: 200,
    emojiFontSize: '1.5rem', nameVariant: 'body2', detailVariant: 'caption',
    padding: 1, gap: 0.5,
  },
};

/** Tier for a roster of `memberCount` members. Thresholds are chosen so a
 *  typical household (up to four) never leaves the roomy tier. */
export function densityFor(memberCount: number): Density {
  if (memberCount <= 4) return 'roomy';
  if (memberCount <= 8) return 'medium';
  return 'compact';
}

export function densitySpec(memberCount: number): DensitySpec {
  return SPECS[densityFor(memberCount)];
}
