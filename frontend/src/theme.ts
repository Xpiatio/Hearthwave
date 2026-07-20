import { createTheme, type Theme } from '@mui/material/styles';

export interface ThemeOptionsExtra {
  fontScale?: number;
  highContrast?: boolean;
  /** E-ink wall panels: fixed grayscale black-on-white, no gradients, no
   *  animation. Forces light mode + high contrast regardless of `dark`. */
  eink?: boolean;
}

export function makeTheme(dark: boolean, opts?: ThemeOptionsExtra) {
  const s = opts?.fontScale ?? 1;
  const eink = opts?.eink ?? false;
  // E-ink is reflective — always max-contrast black on paper-white, never dusk.
  if (eink) dark = false;
  const hc = eink || (opts?.highContrast ?? false);
  return createTheme({
    palette: {
      mode: dark ? 'dark' : 'light',
      primary: {
        main: hc ? (dark ? '#99CCFF' : '#003399') : dark ? '#60A5FA' : '#2563EB',
        dark: hc ? (dark ? '#66B2FF' : '#002266') : dark ? '#2563EB' : '#1D4ED8',
      },
      info: {
        main: dark ? '#93C5FD' : '#1E4976',
      },
      warning: {
        main: dark ? '#FBBF24' : '#7a4a00',
      },
      error: {
        main: hc ? (dark ? '#FF6666' : '#990000') : dark ? '#F87171' : '#B91C1C',
      },
      success: {
        main: dark ? '#4ADE80' : '#15803D',
      },
      background: {
        default: hc ? (dark ? '#000000' : '#FFFFFF') : dark ? '#0F2540' : '#E8EEF7',
        paper: hc ? (dark ? '#0A0A0A' : '#F5F5F5') : dark ? '#1A3A5C' : '#C8D8EC',
      },
      text: {
        primary: hc ? (dark ? '#FFFFFF' : '#000000') : dark ? '#F9FAFB' : '#0F2540',
      },
      divider: hc
        ? dark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.7)'
        : dark ? 'rgba(37,99,235,0.3)' : 'rgba(30,73,118,0.25)',
    },
    typography: {
      htmlFontSize: 16,
      fontSize: 14 * s,
      fontFamily:
        "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      body1: { fontSize: `${1.125 * s}rem` },
      body2: { fontSize: `${1 * s}rem` },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            minHeight: 48,
            fontWeight: 700,
            letterSpacing: '0.04em',
          },
          sizeLarge: {
            minHeight: 56,
            fontSize: '1rem',
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            minHeight: 44,
            minWidth: 44,
          },
        },
      },
      MuiButtonBase: {
        styleOverrides: {
          root: ({ theme }) => ({
            '&.Mui-focusVisible': {
              outline: `3px solid ${theme.palette.primary.main}`,
              outlineOffset: 2,
            },
          }),
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            fontSize: `${1.125 * s}rem`,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: ({ theme }) => ({
            border: `1px solid ${theme.palette.divider}`,
          }),
          rounded: {
            borderRadius: 8,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            overflow: 'hidden',
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: eink
              ? '#FFFFFF'
              : theme.palette.mode === 'dark' ? '#0F2540' : '#C8D8EC',
            border: 'none',
            borderRadius: 0,
            color: eink ? '#000000' : theme.palette.mode === 'dark' ? '#F9FAFB' : '#0F2540',
          }),
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: ({ theme }) => ({
            // Flat white-on-black bar for e-ink — gradients smear on refresh.
            background: eink
              ? '#FFFFFF'
              : theme.palette.mode === 'dark'
                ? 'linear-gradient(135deg, #0F2540 0%, #1E4976 100%)'
                : 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)',
            color: eink ? '#000000' : '#F9FAFB',
            fontWeight: 700,
          }),
        },
      },
    },
    // E-ink panels smear on animation — kill all MUI transitions.
    ...(eink ? { transitions: { create: () => 'none' } } : {}),
  });
}

export function withTouchDensity(theme: Theme): Theme {
  return createTheme(theme, {
    components: {
      MuiButton: {
        styleOverrides: {
          root: { minHeight: 56 },
          sizeLarge: { minHeight: 64 },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: { minHeight: 52, minWidth: 52 },
        },
      },
    },
  });
}
