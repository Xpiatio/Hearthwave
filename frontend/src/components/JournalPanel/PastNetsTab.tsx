import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Chip,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableSortLabel,
  TextField,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type {
  AttendanceStatRow,
  NetSessionDetail,
  NetSessionRosterRow,
  NetSessionSummary,
} from '../../types/ws';
import { downloadText } from '../../utils/download';
import { sessionToCsv, allSessionsToCsv } from '../../netsessions/csv';
import { useRosterSort } from '../../netsessions/rosterView';
import { netDate } from '../../netsessions/dates';

type RosterColumn = 'callsign' | 'name' | 'location' | 'status' | 'traffic';

/** Fields this table renders — a filter query should never match a hidden
 *  field (e.g. the raw checkin_time) the user can't see in this view. */
const PAST_NETS_SEARCH_FIELDS: (keyof NetSessionRosterRow)[] = [
  'callsign', 'name', 'location', 'status', 'traffic',
];

interface Props {
  sessions: NetSessionSummary[];
  stats: AttendanceStatRow[];
  selected: NetSessionDetail | null;
  isAdmin: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const NET_TYPE_LABELS: Record<string, string> = {
  ncs: 'Net Control',
  neighborhood: 'Neighborhood',
};

function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  return `${minutes} min`;
}

export function PastNetsTab({
  sessions,
  stats,
  selected,
  isAdmin,
  onSelect,
  onDelete,
}: Props) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Filtering/sorting only ever changes what's displayed here — CSV export
  // and delete both operate on `selected` (the full session), never on this
  // derived view. resetKey clears the query/sort whenever the selected
  // session changes, so a filter that emptied one net's roster can't also
  // silently hide rows in the next net you pick.
  const {
    rosterQuery,
    setRosterQuery,
    sortColumn,
    handleSort,
    sortDirection,
    visibleRoster,
    showFilterInput,
  } = useRosterSort<NetSessionRosterRow, RosterColumn>(
    selected?.roster ?? [],
    PAST_NETS_SEARCH_FIELDS,
    selected?.id ?? null,
  );

  function handleDelete(id: string) {
    if (confirmDelete === id) {
      onDelete(id);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(id);
    }
  }

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left: session list */}
      <Box
        sx={{
          width: 240,
          borderRight: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <Box sx={{ flex: 1, overflowY: 'auto' }}>
          {sessions.length === 0 ? (
            <Typography
              variant="body2"
              sx={{ color: 'text.secondary', p: 1.5, fontStyle: 'italic' }}
            >
              No nets recorded yet. Records appear here after a net ends.
            </Typography>
          ) : (
            <List dense disablePadding aria-label="Past nets">
              {sessions.map((s) => (
                <ListItem key={s.id} disablePadding>
                  <ListItemButton
                    selected={selected?.id === s.id}
                    onClick={() => onSelect(s.id)}
                  >
                    <ListItemText
                      primary={netDate(s.started_at)}
                      secondary={`${NET_TYPE_LABELS[s.net_type] ?? s.net_type} · ${s.checkin_count} check-ins · ${formatDuration(s.duration_seconds)}`}
                      slotProps={{
                        primary: {
                          variant: 'body2',
                          sx: { fontWeight: selected?.id === s.id ? 700 : 400 },
                        },
                        secondary: { variant: 'caption' },
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {sessions.length > 0 && (
          <Box sx={{ p: 1, borderTop: 1, borderColor: 'divider' }}>
            <Button
              fullWidth
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={() =>
                downloadText(allSessionsToCsv(sessions), 'net-history.csv', 'text/csv')
              }
            >
              EXPORT ALL (CSV)
            </Button>
          </Box>
        )}
      </Box>

      {/* Right: detail + stats */}
      <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
        {selected ? (
          <Box sx={{ mb: 3 }}>
            <Typography variant="caption" color="text.secondary">
              {selected.started_at} → {selected.ended_at}
            </Typography>
            <Typography variant="h5" sx={{ mt: 0.5, mb: 2 }}>
              {NET_TYPE_LABELS[selected.net_type] ?? selected.net_type} net —{' '}
              {netDate(selected.started_at)}
            </Typography>

            {showFilterInput && (
              <Box sx={{ mb: 1 }}>
                <TextField
                  size="small"
                  fullWidth
                  placeholder="Filter roster"
                  value={rosterQuery}
                  onChange={(e) => setRosterQuery(e.target.value)}
                  slotProps={{ htmlInput: { 'aria-label': 'Filter roster' } }}
                />
              </Box>
            )}

            <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>
                      <TableSortLabel
                        active={sortColumn === 'callsign'}
                        direction={sortColumn === 'callsign' ? sortDirection : 'asc'}
                        onClick={() => handleSort('callsign')}
                      >
                        Callsign
                      </TableSortLabel>
                    </TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>
                      <TableSortLabel
                        active={sortColumn === 'name'}
                        direction={sortColumn === 'name' ? sortDirection : 'asc'}
                        onClick={() => handleSort('name')}
                      >
                        Name
                      </TableSortLabel>
                    </TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>
                      <TableSortLabel
                        active={sortColumn === 'location'}
                        direction={sortColumn === 'location' ? sortDirection : 'asc'}
                        onClick={() => handleSort('location')}
                      >
                        Location
                      </TableSortLabel>
                    </TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>
                      <TableSortLabel
                        active={sortColumn === 'status'}
                        direction={sortColumn === 'status' ? sortDirection : 'asc'}
                        onClick={() => handleSort('status')}
                      >
                        Status
                      </TableSortLabel>
                    </TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>
                      <TableSortLabel
                        active={sortColumn === 'traffic'}
                        direction={sortColumn === 'traffic' ? sortDirection : 'asc'}
                        onClick={() => handleSort('traffic')}
                      >
                        Traffic
                      </TableSortLabel>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {visibleRoster.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} sx={{ color: 'text.secondary' }}>
                        No stations match your filter.
                      </TableCell>
                    </TableRow>
                  ) : (
                    visibleRoster.map((r, i) => (
                      <TableRow key={`${r.callsign}-${r.name}-${i}`}>
                        <TableCell>{r.callsign}</TableCell>
                        <TableCell>{r.name}</TableCell>
                        <TableCell>{r.location}</TableCell>
                        <TableCell>{r.status}</TableCell>
                        <TableCell>{r.traffic ?? ''}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>

            {selected.transcript && (
              <Accordion sx={{ mb: 2 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">Net transcript</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box
                    component="pre"
                    sx={{ fontSize: '0.875rem', overflowX: 'auto', whiteSpace: 'pre-wrap', m: 0 }}
                  >
                    {selected.transcript}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                size="small"
                startIcon={<DownloadIcon />}
                onClick={() =>
                  downloadText(sessionToCsv(selected), `${selected.id}.csv`, 'text/csv')
                }
              >
                DOWNLOAD CSV
              </Button>
              {isAdmin && (
                <Button
                  variant="outlined"
                  size="small"
                  color={confirmDelete === selected.id ? 'error' : 'inherit'}
                  startIcon={<DeleteIcon />}
                  onClick={() => handleDelete(selected.id)}
                  aria-label={
                    confirmDelete === selected.id ? 'Confirm delete' : 'Delete net record'
                  }
                >
                  {confirmDelete === selected.id ? 'CONFIRM DELETE' : 'DELETE'}
                </Button>
              )}
            </Box>
          </Box>
        ) : (
          <Typography sx={{ color: 'text.secondary', fontStyle: 'italic', mb: 3 }}>
            Select a net to see its roster.
          </Typography>
        )}

        {stats.length > 0 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>ATTENDANCE</Typography>
            <List dense disablePadding aria-label="Attendance statistics">
              {stats.map((row) => (
                <ListItem key={row.callsign} disableGutters>
                  <ListItemText
                    primary={`${row.name || row.callsign} (${row.callsign})`}
                    secondary={`${row.total_nets} nets · ${row.attended_of_recent} of last ${row.recent_window} · streak ${row.current_streak}`}
                    slotProps={{
                      primary: { variant: 'body2' },
                      secondary: { variant: 'caption' },
                    }}
                  />
                  {row.current_streak >= 3 && (
                    <Chip label={`${row.current_streak} in a row`} size="small" color="success" />
                  )}
                </ListItem>
              ))}
            </List>
          </Box>
        )}
      </Box>
    </Box>
  );
}
