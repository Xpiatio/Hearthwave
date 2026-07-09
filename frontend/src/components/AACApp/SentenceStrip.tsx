import { Box, Button, Chip, Paper, Typography } from '@mui/material';
import BackspaceIcon from '@mui/icons-material/Backspace';
import ClearAllIcon from '@mui/icons-material/ClearAll';

interface Props {
  chunks: string[];
  onBackspace: () => void;
  onClear: () => void;
}

export function SentenceStrip({ chunks, onBackspace, onClear }: Props) {
  return (
    <Paper
      square
      elevation={0}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        p: 1,
        minHeight: 72,
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Box
        role="status"
        aria-live="polite"
        aria-label="Message being composed"
        sx={{ flex: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}
      >
        {chunks.length === 0 ? (
          <Typography color="text.secondary" sx={{ fontStyle: 'italic' }}>
            Tap buttons to build your message
          </Typography>
        ) : (
          chunks.map((c, i) => (
            <Chip key={i} label={c} sx={{ fontSize: '1.1rem', height: 40 }} />
          ))
        )}
      </Box>
      <Button
        variant="outlined"
        onClick={onBackspace}
        disabled={chunks.length === 0}
        aria-label="Remove last word"
        startIcon={<BackspaceIcon />}
        sx={{ minHeight: 56 }}
      >
        Undo
      </Button>
      <Button
        variant="outlined"
        color="warning"
        onClick={onClear}
        disabled={chunks.length === 0}
        aria-label="Clear message"
        startIcon={<ClearAllIcon />}
        sx={{ minHeight: 56 }}
      >
        Clear
      </Button>
    </Paper>
  );
}
