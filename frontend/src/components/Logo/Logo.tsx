import { useId } from 'react';
import { Box } from '@mui/material';

interface LogoProps {
  /** Pixel size of the square mark. Default 32. */
  size?: number;
  /** When true, renders the "Hearthwave" wordmark beside the mark. */
  withWordmark?: boolean;
}

/**
 * Hearthwave logo — a home sheltering a radio set, with signal waves
 * cresting off the roof. The house and radio strokes are a fixed cyan and
 * the waves sweep cyan → violet → magenta, matching the brand mark in both
 * light and dark themes.
 */
export function Logo({ size = 32, withWordmark = false }: LogoProps) {
  // Unique gradient id so multiple Logo instances don't collide.
  const gradId = useId();
  const cyan = '#20C5CE';

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
      <defs>
        <linearGradient id={gradId} x1="55" y1="20" x2="95" y2="50" gradientUnits="userSpaceOnUse">
          <stop stopColor="#36DDE4" />
          <stop offset="0.5" stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#EA53C6" />
        </linearGradient>
      </defs>
      {/* house */}
      <path d="M16 54 L50 26 L84 54 V86 H16 Z" stroke={cyan} strokeWidth={5} strokeLinejoin="round" />
      {/* radio set inside */}
      <rect x="38" y="58" width="24" height="20" rx="3" stroke={cyan} strokeWidth={3.5} />
      <line x1="43" y1="64" x2="57" y2="64" stroke={cyan} strokeWidth={2.6} strokeLinecap="round" />
      <line x1="43" y1="70" x2="53" y2="70" stroke={cyan} strokeWidth={2.6} strokeLinecap="round" />
      {/* signal waves cresting off the roof */}
      <g stroke={`url(#${gradId})`} strokeWidth={5} strokeLinecap="round">
        <path d="M58 30 A14 14 0 0 1 72 44" />
        <path d="M62 22 A24 24 0 0 1 86 46" />
        <path d="M66 14 A34 34 0 0 1 100 48" />
      </g>
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
