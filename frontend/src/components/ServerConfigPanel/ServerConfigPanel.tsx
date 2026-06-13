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
  List,
  ListItem,
  ListItemText,
  IconButton,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';

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

// Final-pass model re-transcribes the whole utterance once it ends, replacing
// the stitched-together streaming partials. "" disables the second pass.
const FINAL_WHISPER_MODELS = [
  { value: '',                label: 'Off — single-pass (streaming only)' },
  { value: 'medium.en',       label: 'medium.en' },
  { value: 'large-v3',        label: 'large-v3' },
  { value: 'distil-large-v3', label: 'distil-large-v3 — recommended' },
];

export interface ServerConfig {
  vadThreshold: number;
  whisperModel: string;
  whisperModelFinal: string;
  squelchAdaptive: boolean;
  sttDebugCapture: boolean;
  txConditioning: boolean;
  pttMode: string;
  pttSerialPort: string;
  pttSerialLine: string;
  monitorPassthrough: boolean;
  attendanceEnabled: boolean;
  savedPhrases: string[];
}

export interface ServerConfigSaveValues {
  vad_threshold: number;
  whisper_model: string;
  whisper_model_final: string;
  squelch_adaptive: boolean;
  stt_debug_capture: boolean;
  tx_conditioning: boolean;
  ptt_mode: string;
  ptt_serial_port: string;
  ptt_serial_line: string;
  monitor_passthrough: boolean;
  attendance_enabled: boolean;
  saved_phrases: string[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  config: ServerConfig;
  onSave: (values: ServerConfigSaveValues) => void;
  /** When true, render just the form body (no Dialog chrome) for embedding in
   *  a tabbed SettingsDialog. The Save button is kept; Cancel/title are not. */
  embedded?: boolean;
}

export function ServerConfigPanel({ open, onClose, config, onSave, embedded = false }: Props) {
  const [vadThreshold, setVadThreshold] = useState(0.5);
  const [whisperModel, setWhisperModel] = useState('small.en');
  const [whisperModelFinal, setWhisperModelFinal] = useState('');
  const [squelchAdaptive, setSquelchAdaptive] = useState(false);
  const [sttDebugCapture, setSttDebugCapture] = useState(false);
  const [txConditioning, setTxConditioning] = useState(false);
  const [pttMode, setPttMode] = useState('manual');
  const [pttSerialPort, setPttSerialPort] = useState('');
  const [pttSerialLine, setPttSerialLine] = useState('RTS');
  const [monitorPassthrough, setMonitorPassthrough] = useState(false);
  const [attendanceEnabled, setAttendanceEnabled] = useState(false);
  const [savedPhrases, setSavedPhrases] = useState<string[]>([]);
  const [newPhrase, setNewPhrase] = useState('');

  // Re-initialize only when dialog opens — prevent live WS updates from
  // resetting in-progress edits.
  useEffect(() => {
    if (!open) return;
    setVadThreshold(config.vadThreshold);
    setWhisperModel(config.whisperModel);
    setWhisperModelFinal(config.whisperModelFinal);
    setSquelchAdaptive(config.squelchAdaptive);
    setSttDebugCapture(config.sttDebugCapture);
    setTxConditioning(config.txConditioning);
    setPttMode(config.pttMode);
    setPttSerialPort(config.pttSerialPort);
    setPttSerialLine(config.pttSerialLine);
    setMonitorPassthrough(config.monitorPassthrough);
    setAttendanceEnabled(config.attendanceEnabled);
    setSavedPhrases(config.savedPhrases ?? []);
    setNewPhrase('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleAddPhrase() {
    const trimmed = newPhrase.trim();
    if (!trimmed || savedPhrases.includes(trimmed)) return;
    setSavedPhrases((prev) => [...prev, trimmed]);
    setNewPhrase('');
  }

  function handleRemovePhrase(phrase: string) {
    setSavedPhrases((prev) => prev.filter((p) => p !== phrase));
  }

  function handleSave() {
    onSave({
      vad_threshold: vadThreshold,
      whisper_model: whisperModel,
      whisper_model_final: whisperModelFinal,
      squelch_adaptive: squelchAdaptive,
      stt_debug_capture: sttDebugCapture,
      tx_conditioning: txConditioning,
      ptt_mode: pttMode,
      ptt_serial_port: pttSerialPort.trim(),
      ptt_serial_line: pttSerialLine,
      monitor_passthrough: monitorPassthrough,
      attendance_enabled: attendanceEnabled,
      saved_phrases: savedPhrases,
    });
    onClose();
  }

  const content = (
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

          <FormControl size="small" fullWidth>
            <InputLabel id="whisper-model-final-label">Final-pass Model</InputLabel>
            <Select
              labelId="whisper-model-final-label"
              label="Final-pass Model"
              value={whisperModelFinal}
              displayEmpty
              onChange={(e) => setWhisperModelFinal(e.target.value)}
            >
              {FINAL_WHISPER_MODELS.map((m) => (
                <MenuItem key={m.value || 'off'} value={m.value}>{m.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Re-transcribes each finished transmission with a larger model for higher
            accuracy, replacing the live partials. The model must be staged first
            (e.g. <code>setup.sh --final-model distil-large-v3</code>) and adds ~1.5&nbsp;GB
            RAM while active.
          </Typography>

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

          <FormControlLabel
            control={
              <Switch
                checked={squelchAdaptive}
                onChange={(e) => setSquelchAdaptive(e.target.checked)}
                size="small"
              />
            }
            label="Adaptive squelch"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Track the channel noise floor and open at 3× it, so weak carriers pre-trigger
            capture instead of clipping the first word.
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={txConditioning}
                onChange={(e) => setTxConditioning(e.target.checked)}
                size="small"
              />
            }
            label="TX conditioning"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Band-limit, compress, and level synthesized speech before it drives the radio
            mic — clearer over narrowband FM. Browser read-aloud is unaffected.
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={sttDebugCapture}
                onChange={(e) => setSttDebugCapture(e.target.checked)}
                size="small"
              />
            }
            label="STT debug capture"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Save raw / segmented / processed audio plus transcripts per utterance for
            offline word-error-rate evaluation. For tuning only — leave off normally.
          </Typography>

          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
              Saved Phrases
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
              Phrases added here are passed to Whisper as vocabulary hints to improve recognition accuracy.
            </Typography>
            {savedPhrases.length > 0 && (
              <List dense disablePadding sx={{ mb: 1, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                {savedPhrases.map((phrase) => (
                  <ListItem
                    key={phrase}
                    disableGutters
                    sx={{ px: 1.5 }}
                    secondaryAction={
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleRemovePhrase(phrase)}
                        aria-label={`Remove phrase "${phrase}"`}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    }
                  >
                    <ListItemText primary={phrase} slotProps={{ primary: { variant: 'body2' } }} />
                  </ListItem>
                ))}
              </List>
            )}
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                size="small"
                placeholder="e.g. roger that"
                value={newPhrase}
                onChange={(e) => setNewPhrase(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddPhrase(); } }}
                fullWidth
              />
              <Button
                variant="outlined"
                size="small"
                onClick={handleAddPhrase}
                disabled={!newPhrase.trim() || savedPhrases.includes(newPhrase.trim())}
                startIcon={<AddIcon />}
                sx={{ whiteSpace: 'nowrap' }}
              >
                Add
              </Button>
            </Box>
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
  );

  const saveButton = (
    <Button onClick={handleSave} variant="contained">Save</Button>
  );

  if (embedded) {
    return (
      <Box sx={{ pt: 1 }}>
        {content}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
          {saveButton}
        </Box>
      </Box>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Server Config</DialogTitle>
      <DialogContent dividers>{content}</DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="outlined">Cancel</Button>
        {saveButton}
      </DialogActions>
    </Dialog>
  );
}
