import { Box, Button, Chip, Paper, Typography } from '@mui/material';
import type { NeighborhoodRosterRow } from '../../types/ws';

export interface RosterListProps {
  roster: NeighborhoodRosterRow[];
  currentCall: string | null;
  myUserId: string;
  onStatusChange: (status: 'checked_in' | 'standby') => void;
}

function statusLabel(status: NeighborhoodRosterRow['status']): string {
  return status === 'checked_in' ? 'Checked in' : 'Standby';
}

/** Checked-in-neighbors roster: name, callsign, location, status, and a
 *  called ✓ marker once a row has taken its round-table turn. The row
 *  matching currentCall gets a "Current turn" marker (text, never
 *  color-only) so the highlight reads the same to a screen reader or in
 *  grayscale as it does at a glance.
 *
 *  The status toggle ("Step away" / "I'm back") only ever appears on the
 *  viewer's own row — the server already restricts cross-user status
 *  changes to coordinators (see neighborhood_status), so the UI mirrors
 *  that by only exposing the control where it can succeed unassisted. */
export function RosterList({ roster, currentCall, myUserId, onStatusChange }: RosterListProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
        Checked-in neighbors
      </Typography>

      {roster.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No one checked in yet.
        </Typography>
      ) : (
        <Box role="list" aria-label="Checked-in neighbors" sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {roster.map((row) => {
            const isCurrent = row.user_id === currentCall;
            const isSelf = row.user_id === myUserId;
            return (
              <Paper
                key={row.user_id}
                role="listitem"
                variant="outlined"
                sx={{
                  p: 1.5,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 0.5,
                  borderColor: isCurrent ? 'primary.main' : 'divider',
                  borderWidth: isCurrent ? 2 : 1,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="body1" sx={{ fontWeight: 700 }}>
                    {row.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {row.callsign}
                  </Typography>
                  {isCurrent && <Chip size="small" color="primary" label="Current turn" />}
                  {row.called && <Chip size="small" label="Called ✓" />}
                </Box>

                <Typography variant="body2" color="text.secondary">
                  {row.location}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                  <Typography variant="body2">{statusLabel(row.status)}</Typography>
                  {isSelf && (
                    <Button
                      size="small"
                      variant="text"
                      onClick={() => onStatusChange(row.status === 'checked_in' ? 'standby' : 'checked_in')}
                    >
                      {row.status === 'checked_in' ? 'Step away' : "I'm back"}
                    </Button>
                  )}
                </Box>
              </Paper>
            );
          })}
        </Box>
      )}
    </Box>
  );
}
