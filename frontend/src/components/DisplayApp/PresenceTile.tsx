import { Box, ButtonBase, Chip, Paper, Typography } from '@mui/material';
import type { ChipProps } from '@mui/material';
import type { FamilyPresenceEntry } from '../../types/ws';
import { deriveStatus } from '../../family/presence';

export interface PresenceTileProps {
  entry: FamilyPresenceEntry;
  now: Date;
  // Kiosk "I'm OK" tap-to-check-in (Task 7). When interactive, the tile
  // becomes a tap target that calls onImOk(entry) to open the confirm dialog.
  interactive?: boolean;
  onImOk?: (entry: FamilyPresenceEntry) => void;
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
export function PresenceTile({ entry, now, interactive, onImOk }: PresenceTileProps) {
  const chip = statusChip(entry, now);

  const card = (
    <Paper
      elevation={2}
      sx={{
        p: 2,
        minHeight: 48,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
        textAlign: 'center',
      }}
    >
      <Box component="span" aria-hidden sx={{ fontSize: '2.5rem', lineHeight: 1 }}>
        {entry.avatar_emoji}
      </Box>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        {entry.display_name}
      </Typography>
      <Chip label={chip.label} color={chip.color} size="medium" />
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
