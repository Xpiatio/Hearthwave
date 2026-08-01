import { describe, it, expect } from 'vitest';
import { netDate } from '../dates';

describe('netDate', () => {
  it('returns an empty string for a blank input', () => {
    expect(netDate('')).toBe('');
  });

  it('falls back to a UTC slice for an unparsable string rather than throwing', () => {
    expect(netDate('not a timestamp')).toBe('not a time');
  });

  it('formats a valid ISO string as YYYY-MM-DD', () => {
    expect(netDate('2026-08-01T19:30:00Z')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('accepts both the Z and +00:00 UTC encodings for the same instant', () => {
    // I4: on-disk records may carry either encoding — the date label must
    // not depend on which one a given session happened to be saved with.
    expect(netDate('2026-08-01T19:30:00Z')).toBe(netDate('2026-08-01T19:30:00+00:00'));
  });

  it('reads the local calendar date, not necessarily the UTC one', () => {
    // I3's actual bug: `.slice(0, 10)` reads the UTC date regardless of the
    // viewer's timezone, mislabeling an evening net. This test can't assert
    // a specific shifted date without pinning the host's timezone, but it
    // does confirm netDate is driven by `Date`/`toLocaleDateString` (which
    // resolve in the viewer's local zone) rather than a raw string slice —
    // for a timestamp exactly on a UTC day boundary, the two must be able
    // to differ depending on the host's offset.
    const utcSlice = '2026-08-01T23:30:00Z'.slice(0, 10);
    const local = netDate('2026-08-01T23:30:00Z');
    const offsetMinutes = new Date('2026-08-01T23:30:00Z').getTimezoneOffset();
    if (offsetMinutes < 0) {
      // Host is ahead of UTC (e.g. positive-offset zones) — local date
      // should be 2026-08-02, not the UTC slice's 2026-08-01.
      expect(local).not.toBe(utcSlice);
    } else {
      // Host is at or behind UTC — 23:30 UTC is still the same local day.
      expect(local).toBe(utcSlice);
    }
  });
});
