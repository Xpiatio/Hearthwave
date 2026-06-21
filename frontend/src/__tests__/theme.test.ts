import { describe, it, expect } from 'vitest';
import { makeTheme, withTouchDensity } from '../theme';

describe('withTouchDensity', () => {
  it('raises button and icon-button minimum touch targets', () => {
    const base = makeTheme(false);
    const touch = withTouchDensity(base);
    expect((touch.components?.MuiButton?.styleOverrides?.root as any).minHeight).toBe(56);
    expect((touch.components?.MuiIconButton?.styleOverrides?.root as any).minHeight).toBe(52);
    expect((touch.components?.MuiIconButton?.styleOverrides?.root as any).minWidth).toBe(52);
  });

  it('preserves palette mode', () => {
    expect(withTouchDensity(makeTheme(true)).palette.mode).toBe('dark');
  });
});
