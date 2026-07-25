import { describe, it, expect } from 'vitest';
import { tileMetrics, SMALLEST_TILE } from './tileSize';

describe('tileMetrics', () => {
  it('gives a small household the largest tiles', () => {
    expect(tileMetrics(1).minWidth).toBe(240);
    expect(tileMetrics(4).minWidth).toBe(240);
  });

  it('steps down through the tiers', () => {
    expect(tileMetrics(5).minWidth).toBe(190);
    expect(tileMetrics(8).minWidth).toBe(190);
    expect(tileMetrics(9).minWidth).toBe(155);
    expect(tileMetrics(12).minWidth).toBe(155);
  });

  it('never shrinks below the floor, however many people', () => {
    expect(tileMetrics(13)).toEqual(SMALLEST_TILE);
    expect(tileMetrics(50)).toEqual(SMALLEST_TILE);
    expect(tileMetrics(500)).toEqual(SMALLEST_TILE);
  });

  it('shrinks monotonically as the count grows', () => {
    const widths = [1, 5, 9, 13, 40].map((n) => tileMetrics(n).minWidth);
    const emoji = [1, 5, 9, 13, 40].map((n) => tileMetrics(n).emojiRem);
    for (let i = 1; i < widths.length; i += 1) {
      expect(widths[i]).toBeLessThanOrEqual(widths[i - 1]);
      expect(emoji[i]).toBeLessThanOrEqual(emoji[i - 1]);
    }
  });

  it('treats an empty board as the largest tier', () => {
    expect(tileMetrics(0).minWidth).toBe(240);
  });
});
