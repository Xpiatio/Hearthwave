import { describe, it, expect } from 'vitest';
import {
  incidentDensityFor,
  incidentDensitySpec,
  rosterDensityFor,
  rosterDensitySpec,
} from '../density';

describe('rosterDensityFor', () => {
  it('keeps a small net in the roomy tier', () => {
    expect(rosterDensityFor(0)).toBe('roomy');
    expect(rosterDensityFor(1)).toBe('roomy');
    expect(rosterDensityFor(6)).toBe('roomy');
  });
  it('steps to medium past six neighbors', () => {
    expect(rosterDensityFor(7)).toBe('medium');
    expect(rosterDensityFor(14)).toBe('medium');
  });
  it('steps to compact past fourteen neighbors', () => {
    expect(rosterDensityFor(15)).toBe('compact');
    expect(rosterDensityFor(60)).toBe('compact');
  });
  it('stays roomier than the family board at the same head count', async () => {
    // A roster row carries name, callsign, location, status and a button, so
    // it needs more width per person than a family presence card does.
    const { densityFor } = await import('../../family/density');
    expect(densityFor(6)).toBe('medium');
    expect(rosterDensityFor(6)).toBe('roomy');
  });
});

describe('rosterDensitySpec', () => {
  it('shrinks columns monotonically as the roster grows', () => {
    const roomy = rosterDensitySpec(3);
    const medium = rosterDensitySpec(10);
    const compact = rosterDensitySpec(20);
    expect(roomy.minColumnPx).toBeGreaterThan(medium.minColumnPx);
    expect(medium.minColumnPx).toBeGreaterThan(compact.minColumnPx);
    expect(roomy.maxColumnPx).toBeGreaterThan(medium.maxColumnPx);
    expect(medium.maxColumnPx).toBeGreaterThan(compact.maxColumnPx);
  });
  it('never lets a tier max fall below its own min', () => {
    for (const count of [1, 7, 15]) {
      const spec = rosterDensitySpec(count);
      expect(spec.maxColumnPx).toBeGreaterThanOrEqual(spec.minColumnPx);
    }
  });
  it('keeps every tier wide enough for a status row with its button', () => {
    for (const count of [1, 7, 15]) {
      expect(rosterDensitySpec(count).minColumnPx).toBeGreaterThanOrEqual(190);
    }
  });
});

describe('incidentDensityFor', () => {
  it('keeps a quiet log in the roomy tier', () => {
    expect(incidentDensityFor(0)).toBe('roomy');
    expect(incidentDensityFor(4)).toBe('roomy');
  });
  it('steps to medium past four incidents', () => {
    expect(incidentDensityFor(5)).toBe('medium');
    expect(incidentDensityFor(10)).toBe('medium');
  });
  it('steps to compact past ten incidents', () => {
    expect(incidentDensityFor(11)).toBe('compact');
    expect(incidentDensityFor(80)).toBe('compact');
  });
  it('tiers earlier than the roster, since a card holds free text', () => {
    expect(rosterDensityFor(6)).toBe('roomy');
    expect(incidentDensityFor(6)).toBe('medium');
  });
});

describe('incidentDensitySpec', () => {
  it('shrinks columns monotonically as the log grows', () => {
    const roomy = incidentDensitySpec(2);
    const medium = incidentDensitySpec(8);
    const compact = incidentDensitySpec(20);
    expect(roomy.minColumnPx).toBeGreaterThan(medium.minColumnPx);
    expect(medium.minColumnPx).toBeGreaterThan(compact.minColumnPx);
    expect(roomy.maxColumnPx).toBeGreaterThan(medium.maxColumnPx);
    expect(medium.maxColumnPx).toBeGreaterThan(compact.maxColumnPx);
  });
  it('never lets a tier max fall below its own min', () => {
    for (const count of [1, 5, 11]) {
      const spec = incidentDensitySpec(count);
      expect(spec.maxColumnPx).toBeGreaterThanOrEqual(spec.minColumnPx);
    }
  });
  it('stays wider than a roster card at every tier — descriptions need the room', () => {
    expect(incidentDensitySpec(2).minColumnPx).toBeGreaterThan(rosterDensitySpec(2).minColumnPx);
    expect(incidentDensitySpec(20).minColumnPx).toBeGreaterThan(rosterDensitySpec(20).minColumnPx);
  });
});
