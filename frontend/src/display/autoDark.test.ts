import { describe, it, expect } from 'vitest';
import { isDuskDark } from './autoDark';

describe('isDuskDark', () => {
  it('dark at 19:00', () => expect(isDuskDark(new Date(2026, 6, 18, 19, 0))).toBe(true));
  it('dark at 23:30', () => expect(isDuskDark(new Date(2026, 6, 18, 23, 30))).toBe(true));
  it('dark at 03:00', () => expect(isDuskDark(new Date(2026, 6, 18, 3, 0))).toBe(true));
  it('light at 07:00', () => expect(isDuskDark(new Date(2026, 6, 18, 7, 0))).toBe(false));
  it('light at 12:00', () => expect(isDuskDark(new Date(2026, 6, 18, 12, 0))).toBe(false));
});
