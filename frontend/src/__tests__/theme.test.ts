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

describe('AppBar (top header) theming', () => {
  function appBarStyle(dark: boolean) {
    const theme = makeTheme(dark);
    const root = theme.components?.MuiAppBar?.styleOverrides?.root as any;
    return root({ theme }) as { backgroundColor: string; color: string };
  }

  it('uses a dark bar with light text in dark mode', () => {
    const style = appBarStyle(true);
    expect(style.backgroundColor).toBe('#0F2540');
    expect(style.color).toBe('#F9FAFB');
  });

  it('uses a light bar with dark text in light mode', () => {
    const style = appBarStyle(false);
    expect(style.backgroundColor).toBe('#C8D8EC');
    expect(style.color).toBe('#0F2540');
  });
});
