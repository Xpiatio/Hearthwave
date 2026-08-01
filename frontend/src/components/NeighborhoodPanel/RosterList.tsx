import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import type { NeighborhoodRosterRow } from '../../types/ws';
import { rosterDensitySpec } from '../../neighborhood/density';
import { filterRoster, sortRoster, type SortDirection } from '../../netsessions/rosterView';

type RosterSortColumn = 'name' | 'callsign' | 'location' | 'status';

export interface RosterListProps {
  roster: NeighborhoodRosterRow[];
  currentCall: string | null;
  myUserId: string;
  onStatusChange: (status: 'checked_in' | 'standby') => void;
  /** Admin-only board wipe. Omitted (not disabled) for everyone else, so a
   *  control that can't succeed never appears. */
  onClear?: () => void;
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
 *  that by only exposing the control where it can succeed unassisted.
 *
 *  Rows sit in an auto-fit grid whose card size comes from the head count, so
 *  a six-person net stays big and glanceable while a twenty-person net still
 *  fits on one screen instead of becoming a scroll. See neighborhood/density.ts. */
export function RosterList({ roster, currentCall, myUserId, onStatusChange, onClear }: RosterListProps) {
  const density = rosterDensitySpec(roster.length);

  const [rosterQuery, setRosterQuery] = useState('');
  const [sortColumn, setSortColumn] = useState<RosterSortColumn | ''>('');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const visibleRoster = useMemo(
    () => sortRoster(filterRoster(roster, rosterQuery), sortColumn || null, sortDirection),
    [roster, rosterQuery, sortColumn, sortDirection],
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Checked-in neighbors
        </Typography>
        {onClear && roster.length > 0 && (
          <Button size="small" color="error" onClick={onClear}>
            Clear check-ins
          </Button>
        )}
      </Box>

      {roster.length > 2 && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Filter roster"
            value={rosterQuery}
            onChange={(e) => setRosterQuery(e.target.value)}
            aria-label="Filter roster"
            sx={{ flex: 1, minWidth: 160 }}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="roster-sort-label">Sort by</InputLabel>
            <Select
              labelId="roster-sort-label"
              label="Sort by"
              value={sortColumn}
              onChange={(e) => setSortColumn(e.target.value as RosterSortColumn | '')}
            >
              <MenuItem value="">None</MenuItem>
              <MenuItem value="name">Name</MenuItem>
              <MenuItem value="callsign">Callsign</MenuItem>
              <MenuItem value="location">Location</MenuItem>
              <MenuItem value="status">Status</MenuItem>
            </Select>
          </FormControl>
          {sortColumn && (
            <Tooltip title={sortDirection === 'asc' ? 'Sorting ascending' : 'Sorting descending'}>
              <IconButton
                size="small"
                onClick={() => setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))}
                aria-label="Toggle sort direction"
              >
                {sortDirection === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          )}
        </Box>
      )}

      {roster.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No one checked in yet.
        </Typography>
      ) : visibleRoster.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No neighbors match your filter.
        </Typography>
      ) : (
        <Box
          role="list"
          aria-label="Checked-in neighbors"
          sx={{
            display: 'grid', gap: 1, justifyContent: 'start',
            // auto-fit packs as many columns as the viewport allows; the tier's
            // max keeps a two-neighbor net from rendering two billboards, and
            // min(…, 100%) stops a card overflowing a phone-width screen.
            gridTemplateColumns:
              `repeat(auto-fit, minmax(min(${density.minColumnPx}px, 100%), ${density.maxColumnPx}px))`,
          }}
        >
          {visibleRoster.map((row) => {
            const isCurrent = row.user_id === currentCall;
            const isSelf = row.user_id === myUserId;
            return (
              <Paper
                key={row.user_id}
                role="listitem"
                variant="outlined"
                sx={{
                  p: density.padding,
                  height: '100%',
                  minWidth: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: density.gap,
                  borderColor: isCurrent ? 'primary.main' : 'divider',
                  borderWidth: isCurrent ? 2 : 1,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: density.gap * 2, flexWrap: 'wrap', minWidth: 0 }}>
                  {/* overflowWrap keeps a long name inside a narrow compact-tier
                      card instead of pushing the card past its grid column. */}
                  <Typography variant={density.nameVariant} sx={{ fontWeight: 700, minWidth: 0, overflowWrap: 'anywhere' }}>
                    {row.name}
                  </Typography>
                  <Typography variant={density.detailVariant} color="text.secondary">
                    {row.callsign}
                  </Typography>
                  {isCurrent && <Chip size="small" color="primary" label="Current turn" sx={{ maxWidth: '100%' }} />}
                  {row.called && <Chip size="small" label="Called ✓" sx={{ maxWidth: '100%' }} />}
                </Box>

                <Typography variant={density.detailVariant} color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
                  {row.location}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: density.gap, mt: 'auto' }}>
                  <Typography variant={density.detailVariant}>{statusLabel(row.status)}</Typography>
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
