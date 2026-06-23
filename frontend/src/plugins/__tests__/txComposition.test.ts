import { describe, it, expect } from 'vitest';
import {
  foldCompositions,
  resolveTxComposition,
  isPluginEnabled,
  type TxComposition,
} from '../index';
import type { PluginManifest } from '../../types/ws';

function meshPlugin(overrides: Partial<PluginManifest> = {}): PluginManifest {
  return {
    id: 'meshcore',
    name: 'MeshCore',
    description: '',
    version: '1.0.0',
    enabled: true,
    conflicts_with: [],
    config_schema: [],
    config: { max_packet_length: 140, prefix_separator: ': ' },
    tx_composition: { max_len_key: 'max_packet_length', separator_key: 'prefix_separator', hint: 'MeshCore' },
    ...overrides,
  };
}

function profile(overrides: Record<string, unknown> = {}) {
  return { display_name: 'Ben', operator_name: 'Benjamin', callsign: 'WX1ABC', ...overrides } as never;
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

describe('resolveTxComposition (declarative)', () => {
  it('returns null when no plugin declares tx_composition', () => {
    const plain = meshPlugin({ tx_composition: null });
    expect(resolveTxComposition([plain], profile())).toBeNull();
  });

  it('returns null when the plugin is disabled', () => {
    expect(resolveTxComposition([meshPlugin({ enabled: false })], profile())).toBeNull();
  });

  it('budgets max length minus the "Name: " prefix', () => {
    // "Ben" (3) + ": " (2) = 5 → 140 - 5 = 135
    expect(resolveTxComposition([meshPlugin()], profile())).toEqual({ maxLength: 135, hint: 'MeshCore' });
  });

  it('falls back operator_name → callsign when no display_name', () => {
    const r = resolveTxComposition([meshPlugin({ config: { max_packet_length: 100, prefix_separator: ': ' } })],
      profile({ display_name: '' }));
    expect(r?.maxLength).toBe(90); // "Benjamin"(8)+": "(2)=10 → 90
  });

  it('uses the full budget when there is no sender name', () => {
    const r = resolveTxComposition([meshPlugin({ config: { max_packet_length: 50, prefix_separator: ': ' } })], null);
    expect(r?.maxLength).toBe(50);
  });

  it('never returns a non-positive budget', () => {
    const r = resolveTxComposition([meshPlugin({ config: { max_packet_length: 2, prefix_separator: ': ' } })], profile());
    expect(r?.maxLength).toBe(1);
  });

  it('folds multiple enabled mesh plugins to the most restrictive', () => {
    const wide = meshPlugin({ id: 'a', config: { max_packet_length: 200, prefix_separator: ': ' } });
    const tight = meshPlugin({ id: 'b', config: { max_packet_length: 50, prefix_separator: ': ' } });
    expect(resolveTxComposition([wide, tight], null)).toEqual({ maxLength: 50, hint: 'MeshCore' });
  });
});

describe('isPluginEnabled', () => {
  it('is true only when the plugin is present and enabled', () => {
    const plugins = [meshPlugin({ id: 'ncs', enabled: true }), meshPlugin({ id: 'x', enabled: false })];
    expect(isPluginEnabled(plugins, 'ncs')).toBe(true);
    expect(isPluginEnabled(plugins, 'x')).toBe(false);
    expect(isPluginEnabled(plugins, 'missing')).toBe(false);
  });
});
