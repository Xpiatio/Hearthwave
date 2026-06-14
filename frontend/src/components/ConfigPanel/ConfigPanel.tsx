import {
  Box, Paper, FormControlLabel, Switch, Divider,
  ToggleButtonGroup, ToggleButton, FormControl, InputLabel, Select, MenuItem, Typography,
} from '@mui/material';
import { PanelHeader } from '../PanelHeader/PanelHeader';
import type { InputDeviceOption, MonitorSinkOption, OutputDeviceOption } from '../../types/ws';

interface Props {
  filterProfanity: boolean;
  fuzzyCallsign: boolean;
  inputDevice: string | number;
  systemMonitorSink: string;
  inputDevices: InputDeviceOption[];
  monitorSinks: MonitorSinkOption[];
  outputDevice: number;
  outputDevices: OutputDeviceOption[];
  spectroColormap: 'viridis' | 'grayscale';
  spectroFreqRange: 'voice' | 'full';
  spectroTimeWindowS: number;
  onToggleProfanity: () => void;
  onToggleFuzzy: () => void;
  onInputDeviceChange: (device: string | number, sink: string) => void;
  onOutputDeviceChange: (device: number) => void;
  onSpectroColormapChange: (cm: 'viridis' | 'grayscale') => void;
  onSpectroFreqRangeChange: (range: 'voice' | 'full') => void;
  onSpectroTimeWindowChange: (s: number) => void;
}

export function ConfigPanel({
  filterProfanity,
  fuzzyCallsign,
  inputDevice,
  systemMonitorSink,
  inputDevices,
  monitorSinks,
  outputDevice,
  outputDevices,
  spectroColormap,
  spectroFreqRange,
  spectroTimeWindowS,
  onToggleProfanity,
  onToggleFuzzy,
  onInputDeviceChange,
  onOutputDeviceChange,
  onSpectroColormapChange,
  onSpectroFreqRangeChange,
  onSpectroTimeWindowChange,
}: Props) {
  const isLoopback = inputDevice === 'system_monitor';

  // Fallback options when the backend hasn't responded yet
  const deviceOptions: InputDeviceOption[] = inputDevices.length > 0
    ? inputDevices
    : [
        { label: 'System Default (microphone)', id: -1 },
        { label: 'System Audio Output (loopback)', id: 'system_monitor' },
      ];

  // Output device drives the radio (TTS is played server-side out this device).
  const outputDeviceOptions: OutputDeviceOption[] = outputDevices.length > 0
    ? outputDevices
    : [{ label: 'System Default (speaker)', id: -1 }];

  return (
    <Paper
      elevation={0}
      square
      sx={{ borderBottom: 1, borderColor: 'divider', overflow: 'hidden' }}
      role="region"
      aria-label="Configuration"
    >
      <PanelHeader title="Configuration" gradient="linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)" />

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', px: 2, py: 1.5 }}>

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

        {/* Audio input source */}
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel id="input-device-label">Audio Input</InputLabel>
          <Select
            labelId="input-device-label"
            label="Audio Input"
            value={String(inputDevice)}
            onChange={(e) => {
              const val = e.target.value;
              const id = val === 'system_monitor' ? 'system_monitor' : Number(val);
              onInputDeviceChange(id, id === 'system_monitor' ? systemMonitorSink : '');
            }}
          >
            {deviceOptions.map((dev) => (
              <MenuItem key={String(dev.id)} value={String(dev.id)}>
                {dev.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {isLoopback && monitorSinks.length > 0 && (
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel id="monitor-sink-label">Output Sink</InputLabel>
            <Select
              labelId="monitor-sink-label"
              label="Output Sink"
              value={systemMonitorSink}
              onChange={(e) => onInputDeviceChange('system_monitor', e.target.value)}
            >
              {monitorSinks.map((s) => (
                <MenuItem key={s.sink_id} value={s.sink_id}>
                  {s.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {/* Audio output to the radio — transmitted TTS plays out this device */}
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel id="output-device-label">Audio Output (to radio)</InputLabel>
          <Select
            labelId="output-device-label"
            label="Audio Output (to radio)"
            value={String(outputDevice)}
            onChange={(e) => onOutputDeviceChange(Number(e.target.value))}
          >
            {outputDeviceOptions.map((dev) => (
              <MenuItem key={String(dev.id)} value={String(dev.id)}>
                {dev.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

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
