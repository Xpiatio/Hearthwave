import { Box, Chip, Button, Typography } from '@mui/material';
import PersonAddIcon from '@mui/icons-material/PersonAdd';

interface PendingStation {
  callsign: string;
  name: string;
  location: string;
}

interface Props {
  stations: PendingStation[];
  onAdd: (station: PendingStation) => void;
  onDismiss: (callsign: string) => void;
  onDismissAll: () => void;
}

export function PendingStationsBar({ stations, onAdd, onDismiss, onDismissAll }: Props) {
  if (stations.length === 0) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 1.5,
        py: 0.75,
        bgcolor: 'warning.light',
        flexWrap: 'wrap',
        borderBottom: 1,
        borderColor: 'warning.main',
      }}
      role="region"
      aria-label="Unrecognized stations"
    >
      <Typography variant="caption" sx={{ fontWeight: 700, color: 'warning.dark', flexShrink: 0 }}>
        UNRECOGNIZED:
      </Typography>

      {stations.map((s) => (
        <Chip
          key={s.callsign}
          label={s.callsign}
          size="small"
          icon={<PersonAddIcon />}
          onClick={() => onAdd(s)}
          onDelete={() => onDismiss(s.callsign)}
          sx={{
            bgcolor: 'warning.main',
            color: 'warning.contrastText',
            fontWeight: 700,
            fontFamily: 'monospace',
            '& .MuiChip-icon': { color: 'inherit' },
            '& .MuiChip-deleteIcon': { color: 'inherit' },
          }}
          aria-label={`Add ${s.callsign} to contacts`}
        />
      ))}

      <Box sx={{ flex: 1 }} />
      <Button
        size="small"
        variant="outlined"
        color="warning"
        onClick={onDismissAll}
        sx={{ flexShrink: 0, borderColor: 'warning.dark', color: 'warning.dark' }}
      >
        Dismiss All
      </Button>
    </Box>
  );
}
