import { describe, expect, it } from 'vitest';
import { makeDefaultGrid, resolveTokens, sanitizeAacGrid } from '../defaultGrid';

describe('makeDefaultGrid', () => {
  it('contains the four starter categories', () => {
    const grid = makeDefaultGrid();
    expect(grid.version).toBe(1);
    expect(grid.categories.map((c) => c.name)).toEqual(['Core', 'Radio', 'Status', 'About me']);
    expect(grid.categories[0].buttons.length).toBeGreaterThan(0);
  });

  it('generates unique ids', () => {
    const grid = makeDefaultGrid();
    const ids = grid.categories.flatMap((c) => [c.id, ...c.buttons.map((b) => b.id)]);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('sanitizeAacGrid', () => {
  it('falls back to default on null', () => {
    expect(sanitizeAacGrid(null).categories.map((c) => c.name)).toContain('Radio');
  });

  it('falls back to default on garbage', () => {
    expect(sanitizeAacGrid('garbage').categories.length).toBeGreaterThan(0);
    expect(sanitizeAacGrid(42).categories.length).toBeGreaterThan(0);
    expect(sanitizeAacGrid([]).categories.length).toBeGreaterThan(0);
  });

  it('falls back to default on unknown version', () => {
    const grid = sanitizeAacGrid({ version: 2, categories: [] });
    expect(grid.version).toBe(1);
    expect(grid.categories.length).toBeGreaterThan(0);
  });

  it('falls back to default when no valid categories survive', () => {
    const grid = sanitizeAacGrid({ version: 1, categories: [{ name: '' }, 'junk'] });
    expect(grid.categories.map((c) => c.name)).toContain('Core');
  });

  it('preserves a valid grid and fills missing fields', () => {
    const grid = sanitizeAacGrid({
      version: 1,
      categories: [
        { name: 'Mine', buttons: [{ label: 'Hi' }, { text: 'Bye' }, { nope: true }] },
      ],
    });
    expect(grid.categories).toHaveLength(1);
    const cat = grid.categories[0];
    expect(cat.name).toBe('Mine');
    expect(cat.emoji).toBe('📁');
    expect(cat.id).toBeTruthy();
    expect(cat.buttons).toHaveLength(2);
    expect(cat.buttons[0]).toMatchObject({ label: 'Hi', text: 'Hi', emoji: '💬' });
    expect(cat.buttons[1]).toMatchObject({ label: 'Bye', text: 'Bye' });
  });

  it('caps categories at 20 and buttons at 40 per category', () => {
    const many = {
      version: 1,
      categories: Array.from({ length: 30 }, (_, i) => ({
        name: `Cat ${i}`,
        buttons: Array.from({ length: 60 }, (_, j) => ({ label: `B${j}` })),
      })),
    };
    const grid = sanitizeAacGrid(many);
    expect(grid.categories).toHaveLength(20);
    expect(grid.categories[0].buttons).toHaveLength(40);
  });
});

describe('resolveTokens', () => {
  it('replaces {Name} and {callsign} case-insensitively', () => {
    expect(resolveTokens('This is {CALLSIGN}, my name is {name}', 'Ben', 'WRXB123'))
      .toBe('This is WRXB123, my name is Ben');
  });

  it('falls back when operator name or callsign missing', () => {
    expect(resolveTokens('{Name} / {callsign}', '', '')).toBe('Operator / my callsign');
  });

  it('strips unresolved tokens', () => {
    expect(resolveTokens('QSY to channel {N} now', 'Ben', 'W1AW')).toBe('QSY to channel now');
  });
});
