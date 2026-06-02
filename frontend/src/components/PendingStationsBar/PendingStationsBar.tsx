import { Box, Chip, Button, Typography } from '@mui/material';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import CancelIcon from '@mui/icons-material/Cancel';

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
      component="section"
      aria-label="Unrecognized stations"
      aria-live="polite"
      aria-atomic="false"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 1.5,
        py: 0.75,
        // Explicit colors so contrast is guaranteed regardless of theme light/dark variants
        bgcolor: 'warning.main',
        color: 'warning.contrastText',
        flexWrap: 'wrap',
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      {/* Visible label is decorative — the section aria-label already provides context */}
      <Typography
        variant="caption"
        aria-hidden="true"
        sx={{ fontWeight: 700, flexShrink: 0, color: 'inherit', opacity: 0.85 }}
      >
        UNRECOGNIZED:
      </Typography>

      {stations.map((s) => {
        const details = [s.name, s.location].filter(Boolean).join(', ');
        const chipAriaLabel = details
          ? `Add ${s.callsign} to contacts — ${details}`
          : `Add ${s.callsign} to contacts`;
        return (
          <Chip
            key={s.callsign}
            label={s.callsign}
            size="small"
            icon={<PersonAddIcon aria-hidden="true" />}
            onClick={() => onAdd(s)}
            onDelete={() => onDismiss(s.callsign)}
            deleteIcon={<CancelIcon aria-label={`Dismiss ${s.callsign}`} />}
            aria-label={chipAriaLabel}
            sx={{
              bgcolor: 'background.paper',
              color: 'text.primary',
              fontWeight: 700,
              fontFamily: 'monospace',
              '& .MuiChip-icon': { color: 'warning.main' },
              '& .MuiChip-deleteIcon': { color: 'text.secondary' },
            }}
          />
        );
      })}

      <Box sx={{ flex: 1 }} aria-hidden="true" />

      <Button
        size="small"
        variant="outlined"
        onClick={onDismissAll}
        aria-label="Dismiss all unrecognized stations"
        sx={{
          flexShrink: 0,
          borderColor: 'warning.contrastText',
          color: 'warning.contrastText',
          '&:hover': { bgcolor: 'rgba(0,0,0,0.1)', borderColor: 'warning.contrastText' },
        }}
      >
        Dismiss All
      </Button>
    </Box>
  );
}
