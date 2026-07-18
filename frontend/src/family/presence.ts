import type { FamilyPresenceEntry } from '../types/ws';

export type MemberStatus = 'ok' | 'on_air' | 'no_word';

const ON_AIR_WINDOW_MS = 10 * 60 * 1000;

// Pure status derivation for one family_presence entry, given the current
// time. Order matters: a recent transmission (on_air) takes priority over a
// same-day "I'm OK" check-in, which in turn takes priority over "no word".
export function deriveStatus(e: FamilyPresenceEntry, now: Date): MemberStatus {
  if (e.last_heard && now.getTime() - new Date(e.last_heard).getTime() < ON_AIR_WINDOW_MS) {
    return 'on_air';
  }
  if (e.last_ok && new Date(e.last_ok).toDateString() === now.toDateString()) {
    return 'ok';
  }
  return 'no_word';
}

// Pure diff helper: which entries in `next` just flipped missed_checkin from
// not-missed to missed, relative to `prev`. Used to fire a browser
// notification exactly once per flip, not on every family_presence broadcast.
export function newlyMissed(
  prev: FamilyPresenceEntry[],
  next: FamilyPresenceEntry[]
): FamilyPresenceEntry[] {
  const prevMissed = new Map(prev.map((e) => [e.user_id, e.missed_checkin]));
  return next.filter((e) => e.missed_checkin && !prevMissed.get(e.user_id));
}
