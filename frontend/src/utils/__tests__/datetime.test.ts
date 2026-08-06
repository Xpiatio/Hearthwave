import { describe, it, expect } from 'vitest';
import { formatMessageTime, isSameLocalDay } from '../datetime';

// Fixed reference so these never depend on the wall clock. Local time, since
// the "same day" question is a local-calendar one.
const NOW = new Date(2026, 7, 6, 14, 30); // Aug 6 2026, 14:30 local

function localIso(y: number, m: number, d: number, h: number, min: number): string {
  return new Date(y, m, d, h, min).toISOString();
}

describe('isSameLocalDay', () => {
  it('is true for two instants on the same local date', () => {
    expect(isSameLocalDay(new Date(2026, 7, 6, 0, 1), new Date(2026, 7, 6, 23, 59))).toBe(true);
  });

  it('is false one minute either side of local midnight', () => {
    expect(isSameLocalDay(new Date(2026, 7, 5, 23, 59), new Date(2026, 7, 6, 0, 1))).toBe(false);
  });

  it('is false for the same day-of-month in a different month or year', () => {
    expect(isSameLocalDay(new Date(2026, 6, 6, 12, 0), NOW)).toBe(false);
    expect(isSameLocalDay(new Date(2025, 7, 6, 12, 0), NOW)).toBe(false);
  });
});

describe('formatMessageTime', () => {
  it('omits the date for a message from today', () => {
    const out = formatMessageTime(localIso(2026, 7, 6, 9, 15), { now: NOW });
    expect(out).not.toMatch(/Aug/);
    expect(out).toMatch(/9:15|09:15/);
  });

  it('prefixes the date for a message from yesterday', () => {
    const out = formatMessageTime(localIso(2026, 7, 5, 21, 40), { now: NOW });
    expect(out).toMatch(/^Aug 5, /);
    expect(out).toMatch(/9:40|21:40/);
  });

  it('prefixes the date across a year boundary', () => {
    const nye = new Date(2026, 0, 1, 0, 30);
    const out = formatMessageTime(localIso(2025, 11, 31, 23, 50), { now: nye });
    expect(out).toMatch(/^Dec 31, /);
  });

  it('pads the hour by default and leaves it unpadded when asked', () => {
    const iso = localIso(2026, 7, 6, 9, 5);
    expect(formatMessageTime(iso, { now: NOW })).toMatch(/\b09:05/);
    expect(formatMessageTime(iso, { now: NOW, padHour: false })).toMatch(/\b9:05/);
  });

  it('treats a missing timestamp as now, so it renders time-only', () => {
    expect(formatMessageTime(undefined, { now: NOW })).toBe(
      formatMessageTime(NOW.toISOString(), { now: NOW }),
    );
  });

  it('accepts both backend ISO flavors', () => {
    // utc_now_iso() emits "...Z"; .isoformat() emits "+00:00" with microseconds.
    const z = formatMessageTime('2026-08-05T21:40:00Z', { now: NOW });
    const offset = formatMessageTime('2026-08-05T21:40:00.123456+00:00', { now: NOW });
    expect(z).toBe(offset);
  });

  it('falls back to now rather than "Invalid Date" on unparseable input', () => {
    expect(formatMessageTime('not a timestamp', { now: NOW })).toBe(
      formatMessageTime(NOW.toISOString(), { now: NOW }),
    );
  });
});
