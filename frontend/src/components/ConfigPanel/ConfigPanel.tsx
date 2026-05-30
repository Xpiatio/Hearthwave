import { Box, Paper, Typography, FormControlLabel, Switch, Button, TextField, Divider, ToggleButtonGroup, ToggleButton } from '@mui/material';
import MicIcon from '@mui/icons-material/Mic';

interface Props {
  filterProfanity: boolean;
  fuzzyCallsign: boolean;
  systemMonitorSink: string;
  spectroColormap: 'viridis' | 'grayscale';
  spectroFreqRange: 'voice' | 'full';
  spectroTimeWindowS: number;
  onToggleProfanity: () => void;
  onToggleFuzzy: () => void;
  onSinkChange: (sink: string) => void;
  onVoiceTest: () => void;
  onSpectroColormapChange: (cm: 'viridis' | 'grayscale') => void;
  onSpectroFreqRangeChange: (range: 'voice' | 'full') => void;
  onSpectroTimeWindowChange: (s: number) => void;
}

export function ConfigPanel({
  filterProfanity,
  fuzzyCallsign,
  systemMonitorSink,
  spectroColormap,
  spectroFreqRange,
  spectroTimeWindowS,
  onToggleProfanity,
  onToggleFuzzy,
  onSinkChange,
  onVoiceTest,
  onSpectroColormapChange,
  onSpectroFreqRangeChange,
  onSpectroTimeWindowChange,
}: Props) {
  return (
    <Paper
      elevation={0}
      square
      sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider' }}
      role="region"
      aria-label="Configuration"
    >
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700, textTransform: 'uppercase' }}>
        Configuration
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>

        {/* Text / content toggles */}
        <FormControlLabel
          control={
            <Switch checked={filterProfanity} onChange={onToggleProfanity} size="small" />
          }
          label="Profanity Filter"
        />

        <FormControlLabel
          control={
            <Switch checked={fuzzyCallsign} onChange={onToggleFuzzy} size="small" />
          }
          label="Fuzzy Callsign Match"
        />

        <Divider orientation="vertical" flexItem />

        <Button
          variant="outlined"
          size="small"
          startIcon={<MicIcon />}
          onClick={onVoiceTest}
          aria-label="Play voice test audio"
        >
          Voice Test
        </Button>

        <Divider orientation="vertical" flexItem />

        <TextField
          label="System Audio Sink"
          size="small"
          value={systemMonitorSink}
          onChange={(e) => onSinkChange(e.target.value)}
          placeholder="e.g. alsa_output.pci-0000_00_1f.3.analog-stereo"
          sx={{ minWidth: 260 }}
          slotProps={{ htmlInput: { style: { fontFamily: 'monospace', fontSize: '0.8rem' } } }}
        />

        <Divider orientation="vertical" flexItem />

        {/* Spectrogram controls */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
          <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary' }}>
            Spectrogram:
          </Typography>

          <ToggleButtonGroup
            size="small"
            exclusive
            value={spectroColormap}
            onChange={(_, v) => v && onSpectroColormapChange(v)}
            aria-label="Spectrogram colormap"
          >
            <ToggleButton value="viridis" aria-label="Viridis colormap">Viridis</ToggleButton>
            <ToggleButton value="grayscale" aria-label="Grayscale colormap">Grayscale</ToggleButton>
          </ToggleButtonGroup>

          <ToggleButtonGroup
            size="small"
            exclusive
            value={spectroFreqRange}
            onChange={(_, v) => v && onSpectroFreqRangeChange(v)}
            aria-label="Spectrogram frequency range"
          >
            <ToggleButton value="voice" aria-label="Voice band 300–3400 Hz">Voice</ToggleButton>
            <ToggleButton value="full" aria-label="Full band 0–8 kHz">Full</ToggleButton>
          </ToggleButtonGroup>

          <ToggleButtonGroup
            size="small"
            exclusive
            value={spectroTimeWindowS}
            onChange={(_, v) => v != null && onSpectroTimeWindowChange(v)}
            aria-label="Spectrogram time window"
          >
            <ToggleButton value={10} aria-label="10 second time window">10s</ToggleButton>
            <ToggleButton value={30} aria-label="30 second time window">30s</ToggleButton>
            <ToggleButton value={60} aria-label="60 second time window">60s</ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>
    </Paper>
  );
}
