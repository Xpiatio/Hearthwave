import { describe, it, expect } from 'vitest';
import { applyTileOrder, reorderIds } from './tileOrder';
import type { FamilyPresenceEntry } from '../types/ws';

function entry(user_id: string): FamilyPresenceEntry {
  return {
    user_id,
    display_name: user_id,
    avatar_emoji: '🙂',
    last_heard: null,
    last_ok: null,
    missed_checkin: false,
  };
}

const ids = (list: FamilyPresenceEntry[]) => list.map((e) => e.user_id);

describe('applyTileOrder', () => {
  const presence = [entry('a'), entry('b'), entry('c')];

  it('leaves presence untouched when no order is stored', () => {
    expect(applyTileOrder(presence, [])).toBe(presence);
  });

  it('reorders to the stored order', () => {
    expect(ids(applyTileOrder(presence, ['c', 'a', 'b']))).toEqual(['c', 'a', 'b']);
  });

  it('ignores ids that are no longer present', () => {
    expect(ids(applyTileOrder(presence, ['gone', 'c', 'a', 'b']))).toEqual(['c', 'a', 'b']);
  });

  it('appends members the order has never seen, in server order', () => {
    const withNew = [...presence, entry('d'), entry('e')];
    expect(ids(applyTileOrder(withNew, ['c', 'a']))).toEqual(['c', 'a', 'b', 'd', 'e']);
  });

  it('never duplicates a member listed twice in the order', () => {
    expect(ids(applyTileOrder(presence, ['b', 'b', 'a']))).toEqual(['b', 'a', 'c']);
  });

  it('handles an empty board', () => {
    expect(applyTileOrder([], ['a', 'b'])).toEqual([]);
  });
});

describe('reorderIds', () => {
  it('moves a tile forward', () => {
    expect(reorderIds(['a', 'b', 'c'], 'a', 'c')).toEqual(['b', 'c', 'a']);
  });

  it('moves a tile backward', () => {
    expect(reorderIds(['a', 'b', 'c'], 'c', 'a')).toEqual(['c', 'a', 'b']);
  });

  it('swaps neighbours', () => {
    expect(reorderIds(['a', 'b', 'c'], 'a', 'b')).toEqual(['b', 'a', 'c']);
  });

  it('is a no-op when the ids match or are unknown', () => {
    const ids = ['a', 'b', 'c'];
    expect(reorderIds(ids, 'a', 'a')).toBe(ids);
    expect(reorderIds(ids, 'zz', 'b')).toBe(ids);
    expect(reorderIds(ids, 'a', 'zz')).toBe(ids);
  });
});
