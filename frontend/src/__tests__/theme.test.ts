import { describe, it, expect } from 'vitest';
import { makeTheme, withTouchDensity } from '../theme';

describe('makeTheme', () => {
  it('defaults unchanged: body1 1.125rem, light background', () => {
    const t = makeTheme(false);
    expect(t.typography.body1.fontSize).toBe('1.125rem');
    expect(t.palette.background.default).toBe('#E8EEF7');
  });

  it('fontScale multiplies typography sizes', () => {
    const t = makeTheme(false, { fontScale: 2 });
    expect(t.typography.body1.fontSize).toBe('2.25rem');
    expect(t.typography.body2.fontSize).toBe('2rem');
    expect(t.typography.fontSize).toBe(28);
  });

  it('highContrast dark uses pure black background and white text', () => {
    const t = makeTheme(true, { highContrast: true });
    expect(t.palette.background.default).toBe('#000000');
    expect(t.palette.text.primary).toBe('#FFFFFF');
  });

  it('highContrast light uses pure white background and black text', () => {
    const t = makeTheme(false, { highContrast: true });
    expect(t.palette.background.default).toBe('#FFFFFF');
    expect(t.palette.text.primary).toBe('#000000');
  });
});

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

describe('Focus ring (MuiButtonBase)', () => {
  it('focus ring uses the active (high-contrast) primary color', () => {
    const t = makeTheme(false, { highContrast: true });
    const override = t.components?.MuiButtonBase?.styleOverrides?.root as (o: { theme: typeof t }) => Record<string, unknown>;
    const styles = override({ theme: t }) as { '&.Mui-focusVisible': { outline: string } };
    expect(styles['&.Mui-focusVisible'].outline).toBe('3px solid #003399');
  });

  it('focus ring uses default primary in light mode without high-contrast', () => {
    const t = makeTheme(false);
    const override = t.components?.MuiButtonBase?.styleOverrides?.root as (o: { theme: typeof t }) => Record<string, unknown>;
    const styles = override({ theme: t }) as { '&.Mui-focusVisible': { outline: string } };
    expect(styles['&.Mui-focusVisible'].outline).toBe('3px solid #2563EB');
  });
});
