import { describe, it, expect } from 'vitest';
import { nextNetLabel } from '../schedule';

describe('nextNetLabel', () => {
  it('returns "" when day/time are unset', () => {
    expect(nextNetLabel('', '', new Date('2026-07-13T00:00:00'))).toBe('');
  });

  it('formats day + 12h time as "Net {Day} {time}"', () => {
    const now = new Date('2026-07-13T00:00:00'); // Monday
    expect(nextNetLabel('tue', '19:00', now)).toBe('Net Tue 7:00 PM');
  });

  it('labels today when the net time is later today', () => {
    const now = new Date('2026-07-14T10:00:00'); // Tuesday, before 19:00
    expect(nextNetLabel('tue', '19:00', now)).toBe('Net Tue 7:00 PM');
  });

  it('labels the same day when the net time already passed today (rolls to next week)', () => {
    const now = new Date('2026-07-14T20:00:00'); // Tuesday, after 19:00
    expect(nextNetLabel('tue', '19:00', now)).toBe('Net Tue 7:00 PM');
  });

  it('returns "" for an invalid time', () => {
    expect(nextNetLabel('tue', '25:99', new Date('2026-07-14T00:00:00'))).toBe('');
  });

  it('returns "" for an invalid day', () => {
    expect(nextNetLabel('someday', '19:00', new Date('2026-07-14T00:00:00'))).toBe('');
  });

  it('is case-insensitive on the day key and formats midnight/noon correctly', () => {
    expect(nextNetLabel('SAT', '00:00', new Date('2026-07-14T00:00:00'))).toBe('Net Sat 12:00 AM');
    expect(nextNetLabel('Sun', '12:30', new Date('2026-07-14T00:00:00'))).toBe('Net Sun 12:30 PM');
  });
});
