import { Box, useTheme } from '@mui/material';

interface LogoProps {
  /** Pixel size of the square mark. Default 32. */
  size?: number;
  /** When true, renders the "Hearthwave" wordmark beside the mark. */
  withWordmark?: boolean;
}

/**
 * Hearthwave logo — a signal lantern casting radio waves, the light a
 * family keeps burning so its own can find the channel. The frame follows
 * the theme (cream on dark, ink on light); the glass and waves stay
 * lamp-gold in both.
 */
export function Logo({ size = 32, withWordmark = false }: LogoProps) {
  const theme = useTheme();
  const frame = theme.palette.mode === 'dark' ? '#F4EDE0' : '#33302A';
  const lamp = '#F5B04C';
  const glass = '#FFD98E';

  const mark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Hearthwave logo"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* radio waves off the glass */}
      <g stroke={lamp} strokeWidth={5} strokeLinecap="round">
        <path d="M73 40 A16 16 0 0 1 73 64" />
        <path d="M81 34 A24 24 0 0 1 81 70" opacity={0.55} />
        <path d="M27 40 A16 16 0 0 0 27 64" />
        <path d="M19 34 A24 24 0 0 0 19 70" opacity={0.55} />
      </g>
      {/* lantern: ring, cap, body, glass, muntins, base */}
      <circle cx="50" cy="15" r="5.5" stroke={frame} strokeWidth={4} />
      <path d="M40 36 L50 21 L60 36 Z" fill={frame} />
      <rect x="37" y="35" width="26" height="38" rx="4" fill={frame} />
      <rect x="42" y="40" width="16" height="28" rx="2" fill={glass} />
      <line x1="50" y1="40" x2="50" y2="68" stroke={frame} strokeWidth={2.8} />
      <line x1="42" y1="54" x2="58" y2="54" stroke={frame} strokeWidth={2.8} />
      <rect x="33" y="73" width="34" height="5.5" rx="2.75" fill={frame} />
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
