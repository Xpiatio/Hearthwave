import { describe, it, expect, beforeEach } from 'vitest';
import {
  foldCompositions,
  registerTxComposition,
  resetTxComposition,
  resolveTxComposition,
  type TxComposition,
} from '../index';
import { meshTxContributor } from '../mesh';

// Minimal ServerConfig-shaped object; the contributor only reads via accessors.
function cfg(overrides: Record<string, unknown> = {}) {
  return {
    meshcoreEnabled: true,
    meshcoreMaxPacketLength: 140,
    meshcorePrefixSeparator: ': ',
    ...overrides,
  } as never;
}

function profile(overrides: Record<string, unknown> = {}) {
  return {
    display_name: 'Ben',
    operator_name: 'Benjamin',
    callsign: 'WX1ABC',
    ...overrides,
  } as never;
}

describe('foldCompositions', () => {
  it('returns null for an empty list', () => {
    expect(foldCompositions([])).toBeNull();
  });

  it('ignores nulls', () => {
    expect(foldCompositions([null, null])).toBeNull();
  });

  it('picks the most restrictive (smallest maxLength)', () => {
    const a: TxComposition = { maxLength: 100, hint: 'A' };
    const b: TxComposition = { maxLength: 60, hint: 'B' };
    expect(foldCompositions([a, b, null])).toBe(b);
  });
});

describe('meshTxContributor', () => {
  const contributor = meshTxContributor({
    enabled: (c) => (c as { meshcoreEnabled: boolean }).meshcoreEnabled,
    maxLen: (c) => (c as { meshcoreMaxPacketLength: number }).meshcoreMaxPacketLength,
    separator: (c) => (c as { meshcorePrefixSeparator: string }).meshcorePrefixSeparator,
    hint: 'MeshCore',
  });

  it('returns null when disabled', () => {
    expect(contributor({ profile: profile(), serverConfig: cfg({ meshcoreEnabled: false }) })).toBeNull();
  });

  it('budgets max length minus the "Name: " prefix', () => {
    // "Ben" (3) + ": " (2) = 5 → 140 - 5 = 135
    const result = contributor({ profile: profile(), serverConfig: cfg() });
    expect(result).toEqual({ maxLength: 135, hint: 'MeshCore' });
  });

  it('falls back operator_name → callsign when no display_name', () => {
    const r = contributor({
      profile: profile({ display_name: '' }),
      serverConfig: cfg({ meshcoreMaxPacketLength: 100 }),
    });
    // "Benjamin" (8) + ": " (2) = 10 → 90
    expect(r?.maxLength).toBe(90);
  });

  it('uses full budget when there is no sender name', () => {
    const r = contributor({ profile: null, serverConfig: cfg({ meshcoreMaxPacketLength: 50 }) });
    expect(r?.maxLength).toBe(50);
  });

  it('never returns a non-positive budget', () => {
    const r = contributor({ profile: profile(), serverConfig: cfg({ meshcoreMaxPacketLength: 2 }) });
    expect(r?.maxLength).toBe(1);
  });
});

describe('resolveTxComposition (registry)', () => {
  beforeEach(() => resetTxComposition());

  it('returns null when nothing is registered', () => {
    expect(resolveTxComposition({ profile: profile(), serverConfig: cfg() })).toBeNull();
  });

  it('folds registered contributors to the most restrictive', () => {
    registerTxComposition(() => ({ maxLength: 120, hint: 'wide' }));
    registerTxComposition(() => ({ maxLength: 40, hint: 'tight' }));
    const r = resolveTxComposition({ profile: profile(), serverConfig: cfg() });
    expect(r).toEqual({ maxLength: 40, hint: 'tight' });
  });
});
