import {
  Box,
  Paper,
  Typography,
  Button,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@mui/material';
import type { AttendanceStation } from '../../types/ws';

interface Props {
  stations: AttendanceStation[];
  onClear: () => void;
  /** When true the panel fills its container's height (e.g. inside a Dialog) instead of sizing to content. */
  fillHeight?: boolean;
}

export function AttendancePanel({ stations, onClear, fillHeight = false }: Props) {
  return (
    <Paper
      square
      elevation={0}
      sx={{
        borderBottom: 1,
        borderColor: 'divider',
        overflow: 'hidden',
        ...(fillHeight && { height: '100%', display: 'flex', flexDirection: 'column' }),
      }}
    >
      <Box
        sx={{
          background: 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          px: 2,
          py: 1,
          flexShrink: 0,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700, color: '#F9FAFB' }}>
          STATIONS HEARD THIS SESSION
        </Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={onClear}
          disabled={stations.length === 0}
          sx={{ color: '#F9FAFB', borderColor: 'rgba(255,255,255,0.4)' }}
        >
          CLEAR
        </Button>
      </Box>

      <Box sx={{ px: 2, py: 1, ...(fillHeight && { flex: 1, overflowY: 'auto' }) }}>
        {stations.length === 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
            No stations heard yet.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small" aria-label="Stations heard this session">
              <TableHead>
                <TableRow>
                  <TableCell scope="col" sx={{ fontWeight: 700 }}>Callsign</TableCell>
                  <TableCell scope="col">Name</TableCell>
                  <TableCell scope="col">Location</TableCell>
                  <TableCell scope="col">GMRS</TableCell>
                  <TableCell scope="col">HAM</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stations.map((s) => (
                  <TableRow key={s.callsign} hover>
                    <TableCell sx={{ fontWeight: 700 }}>{s.callsign}</TableCell>
                    <TableCell>{s.name}</TableCell>
                    <TableCell>{s.location}</TableCell>
                    <TableCell>{s.gmrs}</TableCell>
                    <TableCell>{s.ham}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Paper>
  );
}
