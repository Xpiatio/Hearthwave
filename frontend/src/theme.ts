import { createTheme } from '@mui/material/styles';

// WCAG 2.2 AA color palettes from GMRS-TTY constants
// Light: dark colors on white for ≥4.5:1 contrast
// Dark: light colors on #1F2937 for ≥4.5:1 contrast

export function makeTheme(dark: boolean) {
  return createTheme({
    palette: {
      mode: dark ? 'dark' : 'light',
      primary: {
        main: dark ? '#4ADE80' : '#005f00',
      },
      info: {
        main: dark ? '#60A5FA' : '#003d9e',
      },
      warning: {
        main: dark ? '#FBBF24' : '#7a4a00',
      },
      error: {
        main: dark ? '#F87171' : '#B91C1C',
      },
      success: {
        main: dark ? '#4ADE80' : '#15803D',
      },
      background: {
        default: dark ? '#1F2937' : '#ffffff',
        paper: dark ? '#111827' : '#f0f0f0',
      },
      text: {
        primary: dark ? '#F9FAFB' : '#111111',
      },
    },
    typography: {
      htmlFontSize: 16,
      fontFamily:
        "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      body1: { fontSize: '1.125rem' },
      body2: { fontSize: '1rem' },
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
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            fontSize: '1.125rem',
          },
        },
      },
    },
  });
}
