import { describe, it, expect } from 'vitest';
import { densityFor, densitySpec } from '../density';

describe('densityFor', () => {
  it('keeps a typical household in the roomy tier', () => {
    expect(densityFor(1)).toBe('roomy');
    expect(densityFor(4)).toBe('roomy');
  });
  it('steps to medium past four members', () => {
    expect(densityFor(5)).toBe('medium');
    expect(densityFor(8)).toBe('medium');
  });
  it('steps to compact past eight members', () => {
    expect(densityFor(9)).toBe('compact');
    expect(densityFor(30)).toBe('compact');
  });
  it('treats an empty roster as roomy rather than falling off the tier list', () => {
    expect(densityFor(0)).toBe('roomy');
  });
});

describe('densitySpec', () => {
  it('shrinks columns monotonically as the roster grows', () => {
    const roomy = densitySpec(2);
    const medium = densitySpec(6);
    const compact = densitySpec(12);
    expect(roomy.minColumnPx).toBeGreaterThan(medium.minColumnPx);
    expect(medium.minColumnPx).toBeGreaterThan(compact.minColumnPx);
    expect(roomy.maxColumnPx).toBeGreaterThan(medium.maxColumnPx);
    expect(medium.maxColumnPx).toBeGreaterThan(compact.maxColumnPx);
  });
  it('never lets a tier max fall below its own min', () => {
    for (const count of [1, 5, 9]) {
      const spec = densitySpec(count);
      expect(spec.maxColumnPx).toBeGreaterThanOrEqual(spec.minColumnPx);
    }
  });
});
