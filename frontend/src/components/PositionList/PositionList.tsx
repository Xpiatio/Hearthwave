import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { StationPosition } from '../../types/ws';
import { visuallyHidden } from '../../ui/a11y';
import { COMPASS_WORDS, formatAge, formatDistance, sourceLabel } from './format';

interface Props {
  stations: StationPosition[];
  /** Distance unit. Miles by default — this is a US GMRS/ham application. */
  units?: 'mi' | 'km';
  /** True on e-ink kiosks: no hover, no zebra, higher-contrast text. */
  eink?: boolean;
  /** Overrides the default caption, e.g. on the kiosk. */
  emptyText?: string;
}

/**
 * Stations heard, nearest first.
 *
 * Used both as the operator panel's list view and as the whole of the e-ink
 * kiosk's position display, where a map is unrenderable. The server has
 * already sorted by distance and resolved distance/bearing/age, so this
 * component only formats — it never recomputes geography from coordinates.
 */
export function PositionList({
  stations,
  units = 'mi',
  eink = false,
  emptyText = 'No station positions received yet.',
}: Props) {
  if (stations.length === 0) {
    return (
      <Box sx={{ px: 2, py: 1 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
          {emptyText}
        </Typography>
      </Box>
    );
  }

  return (
    <TableContainer>
      <Table size="small" aria-label="Station positions, nearest first">
        <TableHead>
          <TableRow>
            <TableCell scope="col" sx={{ fontWeight: 700 }}>Station</TableCell>
            <TableCell scope="col">Heard&nbsp;on</TableCell>
            <TableCell scope="col" align="right">Distance</TableCell>
            <TableCell scope="col">Bearing</TableCell>
            <TableCell scope="col" align="right">Age</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {stations.map((s) => (
            <TableRow key={`${s.source}:${s.node_id}`} hover={!eink}>
              {/* The station names the row, so it is the row header — that is
                  what lets a screen reader read "Base, APRS, 2.6 mi" instead
                  of five unlabelled cells. */}
              <TableCell
                component="th"
                scope="row"
                sx={{ fontWeight: 700, color: eink ? '#000' : undefined }}
              >
                {s.label || s.node_id}
              </TableCell>
              <TableCell>{sourceLabel(s.source)}</TableCell>
              <TableCell align="right">{formatDistance(s.distance_km, units)}</TableCell>
              <TableCell>
                {s.compass ? (
                  <>
                    <span aria-hidden="true">{s.compass}</span>
                    <Box component="span" sx={visuallyHidden}>
                      {COMPASS_WORDS[s.compass] ?? s.compass}
                    </Box>
                  </>
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell align="right">{formatAge(s.age_s)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
