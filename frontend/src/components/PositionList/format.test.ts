import { describe, it, expect } from 'vitest';
import { formatAge, formatDistance, sourceLabel } from './format';

describe('formatDistance', () => {
  it('converts to miles by default and keeps a decimal when close', () => {
    expect(formatDistance(4.2, 'mi')).toBe('2.6 mi');
  });

  it('drops the decimal past ten, where it is noise', () => {
    expect(formatDistance(100, 'km')).toBe('100 km');
  });

  it('shows a dash when there is no own position to measure from', () => {
    expect(formatDistance(null, 'mi')).toBe('—');
  });
});

describe('formatAge', () => {
  it.each([
    [5, 'now'],
    [59, 'now'],
    [60, '1m'],
    [3599, '59m'],
    [3600, '1h'],
    [86399, '23h'],
    [86400, '1d+'],
  ])('renders %i seconds as %s', (seconds, expected) => {
    expect(formatAge(seconds)).toBe(expected);
  });
});

describe('sourceLabel', () => {
  it('names the sources the app ships with', () => {
    expect(sourceLabel('aprs_rf')).toBe('APRS');
    expect(sourceLabel('meshcore')).toBe('MeshCore');
  });

  it('passes an unknown third-party plugin id through unchanged', () => {
    expect(sourceLabel('some_other_plugin')).toBe('some_other_plugin');
  });
});
