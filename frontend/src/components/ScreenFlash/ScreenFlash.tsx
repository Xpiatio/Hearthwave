import { Box } from '@mui/material';
import { keyframes } from '@mui/system';

export type FlashKind = 'rx' | 'weather' | 'street' | 'family';

// Visual twin colors: RX = info blue, weather/family = amber, street = red.
const COLORS: Record<FlashKind, string> = {
  rx: '#00B0FF',
  weather: '#FFA000',
  street: '#D32F2F',
  family: '#FFA000',
};

export const VIBRATE_PATTERNS: Record<FlashKind, number[]> = {
  rx: [100],
  weather: [200, 100, 200],
  street: [300, 100, 300, 100, 300],
  family: [200, 100, 200],
};

const pulse = (color: string) => keyframes`
  0%   { box-shadow: inset 0 0 0 0 transparent; }
  15%  { box-shadow: inset 0 0 60px 12px ${color}; }
  40%  { box-shadow: inset 0 0 0 0 transparent; }
  55%  { box-shadow: inset 0 0 60px 12px ${color}; }
  100% { box-shadow: inset 0 0 0 0 transparent; }
`;

/** Screen-edge flash: the hearing-accessible twin of an audio cue.
 *  Purely decorative for AT (the cue's real content is the chat entry /
 *  banner / notification), hence aria-hidden + pointer-events none. */
export function ScreenFlash({ flash }: { flash: { kind: FlashKind; seq: number } | null }) {
  if (!flash) return null;
  const color = COLORS[flash.kind];
  return (
    <Box
      key={flash.seq}
      aria-hidden="true"
      style={{ pointerEvents: 'none' }}
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: (theme) => theme.zIndex.tooltip + 1,
        animation: `${pulse(color)} 1.4s ease-out 1`,
      }}
    />
  );
}
