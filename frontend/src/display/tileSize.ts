/** Presence-tile sizing for the wall kiosk.
 *
 *  Tiles shrink as the household grows so a family of four gets big, readable
 *  cards and a family of fourteen still fits without a wall of scrollbar. The
 *  smallest tier is a floor, not a formula: below ~130px a name and a status
 *  chip stop being legible across a room, so past that point the people band
 *  scrolls instead of shrinking further.
 */
export interface TileMetrics {
  /** Feeds `repeat(auto-fit, minmax(Xpx, 1fr))` on the grid. */
  minWidth: number;
  /** Avatar emoji size, in rem. */
  emojiRem: number;
  /** MUI spacing units for the tile's padding. */
  padding: number;
  chipSize: 'small' | 'medium';
}

const TIERS: Array<{ upTo: number; metrics: TileMetrics }> = [
  { upTo: 4, metrics: { minWidth: 240, emojiRem: 3, padding: 2, chipSize: 'medium' } },
  { upTo: 8, metrics: { minWidth: 190, emojiRem: 2.4, padding: 1.5, chipSize: 'medium' } },
  { upTo: 12, metrics: { minWidth: 155, emojiRem: 1.9, padding: 1.25, chipSize: 'small' } },
];

/** The floor — used for 13+ tiles, and the point past which the band scrolls. */
export const SMALLEST_TILE: TileMetrics = {
  minWidth: 130,
  emojiRem: 1.6,
  padding: 1,
  chipSize: 'small',
};

export function tileMetrics(count: number): TileMetrics {
  for (const tier of TIERS) {
    if (count <= tier.upTo) return tier.metrics;
  }
  return SMALLEST_TILE;
}
