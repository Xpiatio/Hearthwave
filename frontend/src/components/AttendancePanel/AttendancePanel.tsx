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
}

export function AttendancePanel({ stations, onClear }: Props) {
  return (
    <Paper square elevation={0} sx={{ borderBottom: 1, borderColor: 'divider', px: 2, py: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          STATIONS HEARD THIS SESSION
        </Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={onClear}
          disabled={stations.length === 0}
        >
          CLEAR
        </Button>
      </Box>

      {stations.length === 0 ? (
        <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
          No stations heard yet.
        </Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Callsign</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Location</TableCell>
                <TableCell>GMRS</TableCell>
                <TableCell>HAM</TableCell>
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
    </Paper>
  );
}
