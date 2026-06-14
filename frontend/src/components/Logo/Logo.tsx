import { Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';

interface LogoProps {
  /** Pixel size of the square mark. Default 32. */
  size?: number;
  /** When true, renders the "Hearthwave" wordmark beside the mark. */
  withWordmark?: boolean;
}

/**
 * Hearthwave logo — a radio wave cresting into a rooftop over a glowing
 * hearth doorway. Wave/roof strokes follow the active theme; the doorway
 * glow is a fixed warm amber so the "hearth" reads in both color modes.
 */
export function Logo({ size = 32, withWordmark = false }: LogoProps) {
  const theme = useTheme();
  const wave = theme.palette.primary.main;
  const roof = theme.palette.mode === 'dark' ? '#93C5FD' : theme.palette.info.main;

  const mark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Hearthwave logo"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 50 Q31 24 50 37 Q69 50 88 30" fill="none" stroke={wave} strokeWidth={5.5} strokeLinecap="round" />
      <path d="M22 54 L22 82 L78 82 L78 44" fill="none" stroke={roof} strokeWidth={4.5} strokeLinejoin="round" />
      <path d="M44 82 L44 64 Q44 57 51 57 L57 57 Q64 57 64 64 L64 82 Z" fill="#FBBF24" />
    </svg>
  );

  if (!withWordmark) return mark;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {mark}
      <Box
        component="span"
        sx={{ fontWeight: 800, fontSize: size * 0.6, letterSpacing: '0.5px', color: 'text.primary' }}
      >
        Hearthwave
      </Box>
    </Box>
  );
}
