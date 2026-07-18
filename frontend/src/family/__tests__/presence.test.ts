import { describe, it, expect } from 'vitest';
import { deriveStatus, newlyMissed } from '../presence';

const base = { user_id: 'u', display_name: 'U', avatar_emoji: '🙂', missed_checkin: false };
const now = new Date('2026-07-17T15:00:00');

describe('deriveStatus', () => {
  it('on_air heard within 10 min', () => {
    expect(deriveStatus({ ...base, last_heard: '2026-07-17T14:55:00', last_ok: null }, now)).toBe('on_air');
  });
  it('ok when last_ok today', () => {
    expect(
      deriveStatus({ ...base, last_heard: '2026-07-17T08:00:00', last_ok: '2026-07-17T08:00:00' }, now)
    ).toBe('ok');
  });
  it('no_word when ok was yesterday', () => {
    expect(deriveStatus({ ...base, last_heard: null, last_ok: '2026-07-16T08:00:00' }, now)).toBe('no_word');
  });
  it('no_word for all-null', () => {
    expect(deriveStatus({ ...base, last_heard: null, last_ok: null }, now)).toBe('no_word');
  });
});

describe('newlyMissed', () => {
  it('flags an entry that flips from not-missed to missed', () => {
    const prev = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: false }];
    const next = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: true }];
    expect(newlyMissed(prev, next)).toEqual(next);
  });

  it('does not re-flag an entry that was already missed', () => {
    const prev = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: true }];
    const next = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: true }];
    expect(newlyMissed(prev, next)).toEqual([]);
  });

  it('ignores entries that are not missed', () => {
    const prev = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: false }];
    const next = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: false }];
    expect(newlyMissed(prev, next)).toEqual([]);
  });

  it('flags a brand-new entry that arrives already missed', () => {
    const next = [{ ...base, user_id: 'kid1', last_heard: null, last_ok: null, missed_checkin: true }];
    expect(newlyMissed([], next)).toEqual(next);
  });
});
