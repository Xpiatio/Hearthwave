import { createTheme } from '@mui/material/styles';

export function makeTheme(dark: boolean) {
  return createTheme({
    palette: {
      mode: dark ? 'dark' : 'light',
      primary: {
        main: dark ? '#60A5FA' : '#2563EB',
        dark: dark ? '#2563EB' : '#1D4ED8',
      },
      info: {
        main: dark ? '#93C5FD' : '#1E4976',
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
        default: dark ? '#0F2540' : '#E8EEF7',
        paper: dark ? '#1A3A5C' : '#C8D8EC',
      },
      text: {
        primary: dark ? '#F9FAFB' : '#0F2540',
      },
      divider: dark ? 'rgba(37,99,235,0.3)' : 'rgba(30,73,118,0.25)',
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
            backgroundColor:
              theme.palette.mode === 'dark' ? '#0F2540' : '#1A3A5C',
            border: 'none',
            borderRadius: 0,
            color: '#F9FAFB',
          }),
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: ({ theme }) => ({
            background:
              theme.palette.mode === 'dark'
                ? 'linear-gradient(135deg, #0F2540 0%, #1E4976 100%)'
                : 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)',
            color: '#F9FAFB',
            fontWeight: 700,
          }),
        },
      },
    },
  });
}
