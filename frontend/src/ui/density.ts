/** Shared density tiering: how tightly a board packs its cards.
 *
 *  A board of three wants big, glanceable cards; a board of twenty wants to
 *  show everyone at once. Rather than one fixed card size, a board picks a
 *  tier from its item count and scales both the grid's column bounds and the
 *  card's internals with it.
 *
 *  The tier boundaries are per-board, since "a lot of people" means something
 *  different for a household (family/density.ts) than for a neighborhood net
 *  (neighborhood/density.ts). Only the picker is shared.
 */

export type Density = 'roomy' | 'medium' | 'compact';

export interface DensityThresholds {
  /** Largest count that still gets the roomy tier. */
  roomyMax: number;
  /** Largest count that still gets the medium tier. */
  mediumMax: number;
}

/** Tier for `count` items. An empty board is roomy rather than falling off
 *  the end of the tier list. */
export function densityForCount(count: number, thresholds: DensityThresholds): Density {
  if (count <= thresholds.roomyMax) return 'roomy';
  if (count <= thresholds.mediumMax) return 'medium';
  return 'compact';
}
