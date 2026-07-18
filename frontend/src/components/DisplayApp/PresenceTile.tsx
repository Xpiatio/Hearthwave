import { Box, Chip, Paper, Typography } from '@mui/material';
import type { ChipProps } from '@mui/material';
import type { FamilyPresenceEntry } from '../../types/ws';
import { deriveStatus } from '../../family/presence';

export interface PresenceTileProps {
  entry: FamilyPresenceEntry;
  now: Date;
  // Wired in Task 7 (kiosk "I'm OK" tap-to-check-in). This task renders
  // passively only — both props are accepted so callers can pass them
  // ahead of time, but they're ignored until interactive is true.
  interactive?: boolean;
  onImOk?: () => void;
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

/** Passive presence tile for the kiosk display: avatar emoji, name, and a
 *  status chip. `interactive`/`onImOk` are accepted for forward-compat with
 *  Task 7's tap-to-check-in wiring but are ignored here. */
export function PresenceTile({ entry, now }: PresenceTileProps) {
  const chip = statusChip(entry, now);

  return (
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
}
