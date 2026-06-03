import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  FormControlLabel,
  Switch,
} from '@mui/material';

const VAD_MARKS = [
  { value: 0.1, label: '0.1' },
  { value: 0.3, label: '0.3' },
  { value: 0.5, label: '0.5' },
  { value: 0.7, label: '0.7' },
  { value: 0.9, label: '0.9' },
];

const WHISPER_MODELS = [
  { value: 'tiny.en',   label: 'tiny.en — fastest, least accurate' },
  { value: 'base.en',   label: 'base.en — fast, lower accuracy' },
  { value: 'small.en',  label: 'small.en — balanced (default)' },
  { value: 'medium.en', label: 'medium.en — slower, more accurate' },
  { value: 'large-v3',  label: 'large-v3 — slowest, most accurate' },
];

export interface ServerConfig {
  vadThreshold: number;
  whisperModel: string;
  pttMode: string;
  pttSerialPort: string;
  pttSerialLine: string;
  monitorPassthrough: boolean;
  attendanceEnabled: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  config: ServerConfig;
  onSave: (values: {
    vad_threshold: number;
    whisper_model: string;
    ptt_mode: string;
    ptt_serial_port: string;
    ptt_serial_line: string;
    monitor_passthrough: boolean;
    attendance_enabled: boolean;
  }) => void;
}

export function ServerConfigPanel({ open, onClose, config, onSave }: Props) {
  const [vadThreshold, setVadThreshold] = useState(0.5);
  const [whisperModel, setWhisperModel] = useState('small.en');
  const [pttMode, setPttMode] = useState('manual');
  const [pttSerialPort, setPttSerialPort] = useState('');
  const [pttSerialLine, setPttSerialLine] = useState('RTS');
  const [monitorPassthrough, setMonitorPassthrough] = useState(false);
  const [attendanceEnabled, setAttendanceEnabled] = useState(false);

  // Re-initialize only when dialog opens — prevent live WS updates from
  // resetting in-progress edits.
  useEffect(() => {
    if (!open) return;
    setVadThreshold(config.vadThreshold);
    setWhisperModel(config.whisperModel);
    setPttMode(config.pttMode);
    setPttSerialPort(config.pttSerialPort);
    setPttSerialLine(config.pttSerialLine);
    setMonitorPassthrough(config.monitorPassthrough);
    setAttendanceEnabled(config.attendanceEnabled);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleSave() {
    onSave({
      vad_threshold: vadThreshold,
      whisper_model: whisperModel,
      ptt_mode: pttMode,
      ptt_serial_port: pttSerialPort.trim(),
      ptt_serial_line: pttSerialLine,
      monitor_passthrough: monitorPassthrough,
      attendance_enabled: attendanceEnabled,
    });
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Server Config</DialogTitle>

      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Audio / STT
          </Typography>

          <FormControl size="small" fullWidth>
            <InputLabel id="whisper-model-label">Whisper Model</InputLabel>
            <Select
              labelId="whisper-model-label"
              label="Whisper Model"
              value={whisperModel}
              onChange={(e) => setWhisperModel(e.target.value)}
            >
              {WHISPER_MODELS.map((m) => (
                <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
              VAD Sensitivity — {vadThreshold.toFixed(2)}
            </Typography>
            <Slider
              value={vadThreshold}
              min={0.1}
              max={0.9}
              step={0.05}
              marks={VAD_MARKS}
              valueLabelDisplay="auto"
              onChange={(_, v) => setVadThreshold(v as number)}
              aria-label="VAD sensitivity"
              sx={{ mt: 1 }}
            />
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Higher = less sensitive (fewer false triggers). Lower = more sensitive (catches faint speech).
            </Typography>
          </Box>

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            PTT
          </Typography>

          <FormControl size="small" fullWidth>
            <InputLabel id="ptt-mode-label">PTT Mode</InputLabel>
            <Select
              labelId="ptt-mode-label"
              label="PTT Mode"
              value={pttMode}
              onChange={(e) => setPttMode(e.target.value)}
            >
              <MenuItem value="manual">Manual (software button)</MenuItem>
              <MenuItem value="serial">Serial port (RTS/DTR)</MenuItem>
              <MenuItem value="vox">VOX (voice-activated)</MenuItem>
            </Select>
          </FormControl>

          {pttMode === 'serial' && (
            <>
              <TextField
                label="Serial Port"
                size="small"
                value={pttSerialPort}
                onChange={(e) => setPttSerialPort(e.target.value)}
                placeholder="e.g. /dev/ttyUSB0 or COM3"
                slotProps={{ htmlInput: { style: { fontFamily: 'monospace', fontSize: '0.85rem' } } }}
                fullWidth
              />

              <FormControl size="small" fullWidth>
                <InputLabel id="ptt-line-label">PTT Line</InputLabel>
                <Select
                  labelId="ptt-line-label"
                  label="PTT Line"
                  value={pttSerialLine}
                  onChange={(e) => setPttSerialLine(e.target.value)}
                >
                  <MenuItem value="RTS">RTS</MenuItem>
                  <MenuItem value="DTR">DTR</MenuItem>
                </Select>
              </FormControl>
            </>
          )}

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Audio Monitor
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={monitorPassthrough}
                onChange={(e) => setMonitorPassthrough(e.target.checked)}
                size="small"
              />
            }
            label="Monitor passthrough"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Route received audio directly to the output device in real time.
          </Typography>

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Session
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={attendanceEnabled}
                onChange={(e) => setAttendanceEnabled(e.target.checked)}
                size="small"
              />
            }
            label="Attendance tracking"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Log which callsigns are heard during the session.
          </Typography>

        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="outlined">Cancel</Button>
        <Button onClick={handleSave} variant="contained">Save</Button>
      </DialogActions>
    </Dialog>
  );
}
