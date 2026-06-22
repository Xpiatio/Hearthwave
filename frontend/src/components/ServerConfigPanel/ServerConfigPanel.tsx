import { useState, useEffect, forwardRef, useImperativeHandle, useRef } from 'react';
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
  voxPrimerEnabled: boolean;
  voxPrimerMs: number;
  voxPrimerWordEnabled: boolean;
  voxPrimerWord: string;
  pttMode: string;
  pttSerialPort: string;
  pttSerialLine: string;
  monitorPassthrough: boolean;
  attendanceEnabled: boolean;
  savedPhrases: string[];
  meshcoreEnabled: boolean;
  meshcoreSerialPort: string;
  meshcoreBaud: number;
  meshcoreMaxPacketLength: number;
  meshcorePrefixSeparator: string;
  meshcoreChannelIdx: number;
}

export interface ServerConfigSaveValues {
  vad_threshold: number;
  whisper_model: string;
  whisper_model_final: string;
  squelch_adaptive: boolean;
  stt_debug_capture: boolean;
  tx_conditioning: boolean;
  vox_primer_enabled: boolean;
  vox_primer_ms: number;
  vox_primer_word_enabled: boolean;
  vox_primer_word: string;
  ptt_mode: string;
  ptt_serial_port: string;
  ptt_serial_line: string;
  monitor_passthrough: boolean;
  attendance_enabled: boolean;
  saved_phrases: string[];
  meshcore_enabled: boolean;
  meshcore_serial_port: string;
  meshcore_baud: number;
  meshcore_max_packet_length: number;
  meshcore_prefix_separator: string;
  meshcore_channel_idx: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  config: ServerConfig;
  onSave: (values: ServerConfigSaveValues) => void;
  /** When true, render just the form body (no Dialog chrome) for embedding in
   *  a tabbed SettingsDialog. The Save button is kept; Cancel/title are not. */
  embedded?: boolean;
  onRescanVocabulary?: () => void;
  /** When true, suppress the embedded/standalone Save button (e.g. a parent
   *  dialog supplies its own footer Save button via the imperative ref). */
  hideSaveButton?: boolean;
  /** Called whenever the form's dirty state changes relative to the seed
   *  snapshot captured when the panel was last opened or imperatively saved. */
  onDirtyChange?: (dirty: boolean) => void;
}

export interface ServerConfigPanelHandle {
  save(): void;
}

function valuesFromConfig(c: ServerConfig): ServerConfigSaveValues {
  return {
    vad_threshold: c.vadThreshold,
    whisper_model: c.whisperModel,
    whisper_model_final: c.whisperModelFinal,
    squelch_adaptive: c.squelchAdaptive,
    stt_debug_capture: c.sttDebugCapture,
    tx_conditioning: c.txConditioning,
    vox_primer_enabled: c.voxPrimerEnabled,
    vox_primer_ms: c.voxPrimerMs,
    vox_primer_word_enabled: c.voxPrimerWordEnabled,
    vox_primer_word: c.voxPrimerWord.trim(),
    ptt_mode: c.pttMode,
    ptt_serial_port: c.pttSerialPort.trim(),
    ptt_serial_line: c.pttSerialLine,
    monitor_passthrough: c.monitorPassthrough,
    attendance_enabled: c.attendanceEnabled,
    saved_phrases: c.savedPhrases,
    meshcore_enabled: c.meshcoreEnabled,
    meshcore_serial_port: c.meshcoreSerialPort.trim(),
    meshcore_baud: c.meshcoreBaud,
    meshcore_max_packet_length: c.meshcoreMaxPacketLength,
    meshcore_prefix_separator: c.meshcorePrefixSeparator,
    meshcore_channel_idx: c.meshcoreChannelIdx,
  };
}

export const ServerConfigPanel = forwardRef<ServerConfigPanelHandle, Props>(function ServerConfigPanel(
  { open, onClose, config, onSave, embedded = false, onRescanVocabulary, hideSaveButton = false, onDirtyChange },
  ref
) {
  const [vadThreshold, setVadThreshold] = useState(0.5);
  const [whisperModel, setWhisperModel] = useState('small.en');
  const [whisperModelFinal, setWhisperModelFinal] = useState('');
  const [squelchAdaptive, setSquelchAdaptive] = useState(false);
  const [sttDebugCapture, setSttDebugCapture] = useState(false);
  const [txConditioning, setTxConditioning] = useState(false);
  const [voxPrimerEnabled, setVoxPrimerEnabled] = useState(false);
  const [voxPrimerMs, setVoxPrimerMs] = useState(300);
  const [voxPrimerWordEnabled, setVoxPrimerWordEnabled] = useState(false);
  const [voxPrimerWord, setVoxPrimerWord] = useState('transmit');
  const [pttMode, setPttMode] = useState('manual');
  const [pttSerialPort, setPttSerialPort] = useState('');
  const [pttSerialLine, setPttSerialLine] = useState('RTS');
  const [monitorPassthrough, setMonitorPassthrough] = useState(false);
  const [attendanceEnabled, setAttendanceEnabled] = useState(false);
  const [savedPhrases, setSavedPhrases] = useState<string[]>([]);
  const [newPhrase, setNewPhrase] = useState('');
  const [meshcoreEnabled, setMeshcoreEnabled] = useState(false);
  const [meshcoreSerialPort, setMeshcoreSerialPort] = useState('/dev/ttyUSB0');
  const [meshcoreBaud, setMeshcoreBaud] = useState(115200);
  const [meshcoreMaxPacketLength, setMeshcoreMaxPacketLength] = useState(140);
  const [meshcorePrefixSeparator, setMeshcorePrefixSeparator] = useState(': ');
  const [meshcoreChannelIdx, setMeshcoreChannelIdx] = useState(0);

  const seedRef = useRef<string>('');

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
    setVoxPrimerEnabled(config.voxPrimerEnabled);
    setVoxPrimerMs(config.voxPrimerMs);
    setVoxPrimerWordEnabled(config.voxPrimerWordEnabled);
    setVoxPrimerWord(config.voxPrimerWord);
    setPttMode(config.pttMode);
    setPttSerialPort(config.pttSerialPort);
    setPttSerialLine(config.pttSerialLine);
    setMonitorPassthrough(config.monitorPassthrough);
    setAttendanceEnabled(config.attendanceEnabled);
    setSavedPhrases(config.savedPhrases ?? []);
    setNewPhrase('');
    setMeshcoreEnabled(config.meshcoreEnabled);
    setMeshcoreSerialPort(config.meshcoreSerialPort);
    setMeshcoreBaud(config.meshcoreBaud);
    setMeshcoreMaxPacketLength(config.meshcoreMaxPacketLength);
    setMeshcorePrefixSeparator(config.meshcorePrefixSeparator);
    setMeshcoreChannelIdx(config.meshcoreChannelIdx);
    // Compute seed from config directly (state setters are async), mirroring
    // buildValues() serialization.
    seedRef.current = JSON.stringify(valuesFromConfig(config));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // For embedded panels that start open=true (always open), seed on first mount.
  useEffect(() => {
    if (!embedded) return;
    seedRef.current = JSON.stringify(valuesFromConfig(config));
    // Only run on first mount for the embedded case.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleAddPhrase() {
    const trimmed = newPhrase.trim();
    if (!trimmed || savedPhrases.includes(trimmed)) return;
    setSavedPhrases((prev) => [...prev, trimmed]);
    setNewPhrase('');
  }

  function handleRemovePhrase(phrase: string) {
    setSavedPhrases((prev) => prev.filter((p) => p !== phrase));
  }

  function buildValues(): ServerConfigSaveValues {
    return {
      vad_threshold: vadThreshold,
      whisper_model: whisperModel,
      whisper_model_final: whisperModelFinal,
      squelch_adaptive: squelchAdaptive,
      stt_debug_capture: sttDebugCapture,
      tx_conditioning: txConditioning,
      vox_primer_enabled: voxPrimerEnabled,
      vox_primer_ms: voxPrimerMs,
      vox_primer_word_enabled: voxPrimerWordEnabled,
      vox_primer_word: voxPrimerWord.trim(),
      ptt_mode: pttMode,
      ptt_serial_port: pttSerialPort.trim(),
      ptt_serial_line: pttSerialLine,
      monitor_passthrough: monitorPassthrough,
      attendance_enabled: attendanceEnabled,
      saved_phrases: savedPhrases,
      meshcore_enabled: meshcoreEnabled,
      meshcore_serial_port: meshcoreSerialPort.trim(),
      meshcore_baud: meshcoreBaud,
      meshcore_max_packet_length: meshcoreMaxPacketLength,
      meshcore_prefix_separator: meshcorePrefixSeparator,
      meshcore_channel_idx: meshcoreChannelIdx,
    };
  }

  // Report dirty on every render (cheap; React bails out on equal state).
  useEffect(() => {
    onDirtyChange?.(JSON.stringify(buildValues()) !== seedRef.current);
  });

  function commitValues() {
    const values = buildValues();
    onSave(values);
    seedRef.current = JSON.stringify(values);
  }

  useImperativeHandle(ref, () => ({ save: commitValues }));

  function handleSave() { // used only by the embedded/standalone button
    commitValues();
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
                checked={voxPrimerEnabled}
                onChange={(e) => setVoxPrimerEnabled(e.target.checked)}
                size="small"
              />
            }
            label="VOX primer tone"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Prepend a short tone to each transmission so a VOX-keyed radio is fully
            keyed before the message starts (silence won't trip VOX).
          </Typography>
          <TextField
            label="Primer duration (ms)"
            type="number"
            size="small"
            value={voxPrimerMs}
            disabled={!voxPrimerEnabled}
            onChange={(e) => setVoxPrimerMs(Math.max(0, Math.min(2000, Number(e.target.value) || 0)))}
            slotProps={{ htmlInput: { min: 0, max: 2000, step: 50 } }}
            sx={{ maxWidth: 200 }}
          />

          <FormControlLabel
            control={
              <Switch
                checked={voxPrimerWordEnabled}
                onChange={(e) => setVoxPrimerWordEnabled(e.target.checked)}
                size="small"
              />
            }
            label="VOX priming word"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Speak a word (e.g. "transmit") right after the primer tone and before
            the message, so a VOX-keyed radio is keyed on a clear spoken keyword.
            Different radios may need different words.
          </Typography>
          <TextField
            label="Priming word"
            size="small"
            value={voxPrimerWord}
            disabled={!voxPrimerWordEnabled}
            onChange={(e) => setVoxPrimerWord(e.target.value.slice(0, 64))}
            sx={{ maxWidth: 200 }}
          />

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
            {onRescanVocabulary && (
              <Button
                variant="outlined"
                size="small"
                onClick={onRescanVocabulary}
                sx={{ mt: 1 }}
              >
                Rescan vocabulary
              </Button>
            )}
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

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            MeshCore (LoRa mesh bridge)
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={meshcoreEnabled}
                onChange={(e) => setMeshcoreEnabled(e.target.checked)}
                size="small"
              />
            }
            label="Forward transmissions to MeshCore"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Mirror each sent message onto the MeshCore mesh, prefixed with the
            sender's name. Received radio traffic is never forwarded.
          </Typography>

          <TextField
            label="MeshCore device"
            value={meshcoreSerialPort}
            onChange={(e) => setMeshcoreSerialPort(e.target.value)}
            disabled={!meshcoreEnabled}
            size="small"
            fullWidth
            helperText="MeshCore Companion serial device, e.g. /dev/ttyUSB0"
          />

          <TextField
            label="Baud rate"
            type="number"
            value={meshcoreBaud}
            onChange={(e) => setMeshcoreBaud(Number(e.target.value) || 115200)}
            disabled={!meshcoreEnabled}
            size="small"
            fullWidth
          />

          <TextField
            label="Max packet length"
            type="number"
            value={meshcoreMaxPacketLength}
            onChange={(e) => setMeshcoreMaxPacketLength(Math.max(1, Number(e.target.value) || 1))}
            disabled={!meshcoreEnabled}
            size="small"
            fullWidth
            helperText="Characters per mesh packet, including the sender prefix."
          />

          <TextField
            label="Channel index"
            type="number"
            value={meshcoreChannelIdx}
            onChange={(e) => setMeshcoreChannelIdx(Math.max(0, Number(e.target.value) || 0))}
            disabled={!meshcoreEnabled}
            size="small"
            fullWidth
          />

          <TextField
            label="Name separator"
            value={meshcorePrefixSeparator}
            onChange={(e) => setMeshcorePrefixSeparator(e.target.value.slice(0, 16))}
            disabled={!meshcoreEnabled}
            size="small"
            fullWidth
            helperText='Joins the sender name and message, e.g. ": " → "Ben: hello"'
          />

        </Box>
  );

  const saveButton = hideSaveButton ? null : (
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
});
