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
// The bare "DeleteOutline" module doesn't exist in the installed
// @mui/icons-material version; DeleteOutlineOutlined is the same
// outline-trash-can glyph the codebase actually ships.
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import type { NeighborhoodRosterRow } from '../../types/ws';
import { rosterDensitySpec } from '../../neighborhood/density';
import { useRosterSort } from '../../netsessions/rosterView';

type RosterSortColumn = 'name' | 'callsign' | 'location' | 'status';

/** Fields this table actually renders — a filter query should never match a
 *  hidden field the user can't see. */
const ROSTER_SEARCH_FIELDS: (keyof NeighborhoodRosterRow)[] = [
  'name', 'callsign', 'location',
  // `via` renders as the "By radio" chip, so it is visible text and has to be
  // searchable — same list PastNetsTab uses.
  'via',
];

export interface RosterListProps {
  roster: NeighborhoodRosterRow[];
  currentCall: string | null;
  myUserId: string;
  onStatusChange: (status: 'checked_in' | 'standby' | 'checked_out') => void;
  /** Admin-only board wipe. Omitted (not disabled) for everyone else, so a
   *  control that can't succeed never appears. */
  onClear?: () => void;
  /** Coordinator-only radio-row controls. A radio caller has no browser, so
   *  the coordinator is the only one who can move their status. */
  isCoordinator?: boolean;
  onStationStatusChange?: (userId: string, status: 'checked_in' | 'standby' | 'checked_out') => void;
  onRemoveStation?: (userId: string) => void;
}

const STATUS_LABELS: Record<NeighborhoodRosterRow['status'], string> = {
  checked_in: 'Checked in',
  standby: 'Standby',
  checked_out: 'Checked out',
};

const STATUS_COLORS: Record<NeighborhoodRosterRow['status'], 'success' | 'warning' | 'info'> = {
  checked_in: 'success',
  standby: 'warning',
  checked_out: 'info',
};

/** Self-toggle cycle: checked in -> standby -> checked out -> checked in.
 *  Mirrors NCSPanel's CheckedIn/Standby/CheckedOut cycle for the same
 *  reasons — "step away" and "check out" are distinct signals of presence. */
const STATUS_CYCLE: NeighborhoodRosterRow['status'][] = ['checked_in', 'standby', 'checked_out'];

const NEXT_ACTION_LABEL: Record<NeighborhoodRosterRow['status'], string> = {
  checked_in: 'Step away',
  standby: 'Check out',
  checked_out: "I'm back",
};

/** The self-toggle copy above is first-person and reads wrong when a
 *  coordinator moves someone else's station, so radio rows get their own
 *  labels over the same STATUS_CYCLE. */
const STATION_ACTION_LABEL: Record<NeighborhoodRosterRow['status'], string> = {
  checked_in: 'Standby',
  standby: 'Check out',
  checked_out: 'Check back in',
};

function nextStatus(status: NeighborhoodRosterRow['status']): NeighborhoodRosterRow['status'] {
  const at = STATUS_CYCLE.indexOf(status);
  return STATUS_CYCLE[(at + 1) % STATUS_CYCLE.length];
}

/** Checked-in-neighbors roster: name, callsign, location, status, and a
 *  called ✓ marker once a row has taken its round-table turn. The row
 *  matching currentCall gets a "Current turn" marker (text, never
 *  color-only) so the highlight reads the same to a screen reader or in
 *  grayscale as it does at a glance.
 *
 *  The status toggle appears in two forms: the first-person "Step away" /
 *  "Check out" / "I'm back" copy on the viewer's own row, and — for a
 *  coordinator only — third-person "Standby" / "Check out" / "Check back in"
 *  copy plus a remove control on radio rows, since a radio caller has no
 *  browser to operate their own row. The server already restricts
 *  cross-user status changes to coordinators (see neighborhood_status), so
 *  the UI mirrors that by only exposing each control where it can succeed
 *  unassisted.
 *
 *  Rows sit in an auto-fit grid whose card size comes from the head count, so
 *  a six-person net stays big and glanceable while a twenty-person net still
 *  fits on one screen instead of becoming a scroll. See neighborhood/density.ts. */
export function RosterList({
  roster,
  currentCall,
  myUserId,
  onStatusChange,
  onClear,
  isCoordinator,
  onStationStatusChange,
  onRemoveStation,
}: RosterListProps) {
  const density = rosterDensitySpec(roster.length);

  const {
    rosterQuery,
    setRosterQuery,
    sortColumn,
    setSortColumn,
    sortDirection,
    setSortDirection,
    visibleRoster,
    showFilterInput,
  } = useRosterSort<NeighborhoodRosterRow, RosterSortColumn>(roster, ROSTER_SEARCH_FIELDS);

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

      {showFilterInput && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Filter roster"
            value={rosterQuery}
            onChange={(e) => setRosterQuery(e.target.value)}
            slotProps={{ htmlInput: { 'aria-label': 'Filter roster' } }}
            sx={{ flex: 1, minWidth: 160 }}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="roster-sort-label">Sort by</InputLabel>
            <Select
              labelId="roster-sort-label"
              label="Sort by"
              value={sortColumn ?? ''}
              onChange={(e) => setSortColumn((e.target.value || null) as RosterSortColumn | null)}
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
            const isRadio = row.via === 'radio';
            const canOperate = isRadio && !!isCoordinator;
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
                  {isRadio && <Chip size="small" variant="outlined" label="By radio" sx={{ maxWidth: '100%' }} />}
                  {isCurrent && <Chip size="small" color="primary" label="Current turn" sx={{ maxWidth: '100%' }} />}
                  {row.called && <Chip size="small" label="Called ✓" sx={{ maxWidth: '100%' }} />}
                </Box>

                <Typography variant={density.detailVariant} color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
                  {row.location}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: density.gap, mt: 'auto' }}>
                  <Chip size="small" color={STATUS_COLORS[row.status]} label={STATUS_LABELS[row.status]} />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: density.gap }}>
                    {isSelf && (
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => onStatusChange(nextStatus(row.status))}
                      >
                        {NEXT_ACTION_LABEL[row.status]}
                      </Button>
                    )}
                    {canOperate && onStationStatusChange && (
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => onStationStatusChange(row.user_id, nextStatus(row.status))}
                      >
                        {STATION_ACTION_LABEL[row.status]}
                      </Button>
                    )}
                    {canOperate && onRemoveStation && (
                      // No confirm: this row is a coordinator's typo that never
                      // reached disk, and re-adding it costs one pick. Confirms
                      // stay for the board wipe and street alerts.
                      <Tooltip title={`Remove ${row.name}`}>
                        <IconButton
                          size="small"
                          aria-label={`Remove ${row.name}`}
                          onClick={() => onRemoveStation(row.user_id)}
                        >
                          <DeleteOutlineIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
              </Paper>
            );
          })}
        </Box>
      )}
    </Box>
  );
}
