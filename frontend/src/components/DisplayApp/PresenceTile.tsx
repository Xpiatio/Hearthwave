import { Box, ButtonBase, Chip, Paper, Typography } from '@mui/material';
import type { ChipProps } from '@mui/material';
import type { FamilyPresenceEntry } from '../../types/ws';
import { deriveStatus } from '../../family/presence';
import { tileMetrics, type TileMetrics } from '../../display/tileSize';

export interface PresenceTileProps {
  entry: FamilyPresenceEntry;
  now: Date;
  // Kiosk "I'm OK" tap-to-check-in (Task 7). When interactive, the tile
  // becomes a tap target that calls onImOk(entry) to open the confirm dialog.
  interactive?: boolean;
  onImOk?: (entry: FamilyPresenceEntry) => void;
  /** Sizing for the current household size; defaults to the largest tier. */
  metrics?: TileMetrics;
}

// Status label/color mapping: missed_checkin takes priority over
// deriveStatus (a caregiver needs to see "overdue" even if the member
// happens to have checked in or transmitted earlier the same day).
function statusChip(entry: FamilyPresenceEntry, now: Date): { label: string; color: ChipProps['color'] } {
  if (entry.missed_checkin) return { label: 'Missed check-in', color: 'warning' };
  const status = deriveStatus(entry, now);
  if (status === 'on_air') return { label: 'On air', color: 'info' };
  if (status === 'ok') return { label: 'OK', color: 'success' };
  return { label: 'No word', color: 'default' };
}

/** Presence tile for the kiosk display: avatar emoji, name, and a status
 *  chip. In interactive mode (Task 7's tap-to-wake window), the tile becomes
 *  a tap target that opens the "Mark OK?" confirm dialog for this member. */
export function PresenceTile({ entry, now, interactive, onImOk, metrics }: PresenceTileProps) {
  const chip = statusChip(entry, now);
  const size = metrics ?? tileMetrics(1);

  const card = (
    <Paper
      elevation={2}
      sx={{
        p: size.padding,
        minHeight: 48,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
        textAlign: 'center',
      }}
    >
      <Box component="span" aria-hidden sx={{ fontSize: `${size.emojiRem}rem`, lineHeight: 1 }}>
        {entry.avatar_emoji}
      </Box>
      <Typography
        variant="h6"
        sx={{ fontWeight: 700, fontSize: `${Math.max(0.95, size.emojiRem * 0.45)}rem` }}
      >
        {entry.display_name}
      </Typography>
      <Chip label={chip.label} color={chip.color} size={size.chipSize} />
    </Paper>
  );

  if (!interactive) return card;

  return (
    <ButtonBase
      aria-label={entry.display_name}
      onClick={() => onImOk?.(entry)}
      sx={{ display: 'block', width: '100%', textAlign: 'inherit', borderRadius: 1 }}
    >
      {card}
    </ButtonBase>
  );
}
