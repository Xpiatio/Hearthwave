import { Box, Chip, Paper, Typography } from '@mui/material';
import type { ChipProps } from '@mui/material';
import type { FamilyPresenceEntry } from '../../types/ws';
import { deriveStatus } from '../../family/presence';
import { densitySpec } from '../../family/density';
import type { DensitySpec } from '../../family/density';
import { formatMessageTime } from '../../utils/datetime';

interface Props {
  entry: FamilyPresenceEntry;
  now: Date;
  /** Sizing tier from the roster size — see family/density.ts. Defaults to
   *  the roomy (small-household) tier when a caller renders a lone card. */
  density?: DensitySpec;
}

function formatRelative(iso: string | null, now: Date): string {
  if (!iso) return 'never';
  const diffMs = now.getTime() - new Date(iso).getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`;
}

/** Status chip contents: text label always present (never color-only) —
 *  missed_checkin overrides whatever deriveStatus would otherwise say,
 *  since a caregiver needs to see "overdue" even if the member happens to
 *  be transmitting or checked in earlier in the day. */
function statusChip(entry: FamilyPresenceEntry, now: Date): { label: string; color: ChipProps['color'] } {
  if (entry.missed_checkin) return { label: 'Missed check-in', color: 'warning' };
  const status = deriveStatus(entry, now);
  if (status === 'on_air') return { label: 'On air', color: 'info' };
  if (status === 'ok') {
    const time = entry.last_ok ? formatMessageTime(entry.last_ok, { now, padHour: false }) : '';
    return { label: `OK ✓${time ? ` ${time}` : ''}`, color: 'success' };
  }
  return { label: 'No word', color: 'default' };
}

/** Presence card for one family member: avatar, name, status chip, and a
 *  relative "last heard" line. */
export function MemberCard({ entry, now, density = densitySpec(1) }: Props) {
  const chip = statusChip(entry, now);
  return (
    <Paper sx={{ p: density.padding, display: 'flex', flexDirection: 'column', gap: density.gap, height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: density.gap * 1.5, minWidth: 0 }}>
        <Box component="span" aria-hidden sx={{ fontSize: density.emojiFontSize, lineHeight: 1 }}>
          {entry.avatar_emoji}
        </Box>
        {/* overflowWrap keeps a long name inside a narrow compact-tier card
            instead of pushing the card wider than its grid column. */}
        <Typography variant={density.nameVariant} sx={{ fontWeight: 700, minWidth: 0, overflowWrap: 'anywhere' }}>
          {entry.display_name}
        </Typography>
      </Box>
      <Chip size="small" color={chip.color} label={chip.label} sx={{ alignSelf: 'flex-start', maxWidth: '100%' }} />
      <Typography variant={density.detailVariant} color="text.secondary">
        Last heard {formatRelative(entry.last_heard, now)}
      </Typography>
    </Paper>
  );
}
