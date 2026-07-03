import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Paper,
  CircularProgress,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Alert,
} from '@mui/material';
import type { CalibrationResultEntry, WsMessage } from '../../types/ws';

type Step = 'intro' | 'recording' | 'analyzing' | 'results';

interface Props {
  open: boolean;
  onClose: () => void;
  send: (msg: unknown) => void;
  lastMessage: WsMessage | null;
}

function formatWer(wer: number): string {
  return `${(wer * 100).toFixed(1)}%`;
}

function formatCombo(entry: { model: string; gain_mode: string; noise_profile: boolean }): string {
  return `${entry.model} · ${entry.gain_mode} gain · noise profile ${entry.noise_profile ? 'on' : 'off'}`;
}

export function CalibrationDialog({ open, onClose, send, lastMessage }: Props) {
  const [step, setStep] = useState<Step>('intro');
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ index: number; total: number } & Omit<CalibrationResultEntry, 'wer' | 'hypothesis'> | null>(null);
  const [results, setResults] = useState<CalibrationResultEntry[] | null>(null);
  const [recommended, setRecommended] = useState<CalibrationResultEntry | null>(null);
  const [applied, setApplied] = useState(false);
  const [elapsedS, setElapsedS] = useState(0);

  useEffect(() => {
    if (!open) return;
    setStep('intro');
    setError(null);
    setProgress(null);
    setResults(null);
    setRecommended(null);
    setApplied(false);
    setElapsedS(0);
    send({ type: 'calibration_get_text' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (step !== 'recording') return;
    const id = setInterval(() => setElapsedS((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [step]);

  useEffect(() => {
    if (!lastMessage) return;
    switch (lastMessage.type) {
      case 'calibration_text':
        setText(lastMessage.text);
        break;
      case 'calibration_started':
        setError(null);
        setElapsedS(0);
        setStep('recording');
        break;
      case 'calibration_progress':
        setStep('analyzing');
        setProgress(lastMessage);
        break;
      case 'calibration_result':
        setStep('results');
        setResults(lastMessage.results);
        setRecommended(lastMessage.recommended);
        break;
      case 'calibration_error':
        setError(lastMessage.detail);
        break;
      case 'calibration_applied':
        setApplied(true);
        break;
    }
  }, [lastMessage]);

  function handleStart() {
    setError(null);
    send({ type: 'calibration_start' });
  }

  function handleStop() {
    setStep('analyzing');
    setProgress(null);
    send({ type: 'calibration_stop' });
  }

  function handleApply(entry: CalibrationResultEntry) {
    send({
      type: 'calibration_apply',
      whisper_model: entry.model,
      gain_mode: entry.gain_mode,
      noise_profile: entry.noise_profile,
    });
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>STT Calibration</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {step === 'intro' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Key up your radio and read the passage below at a natural pace, then stop
              the recording. Hearthwave will compare what it heard against this known
              text and recommend the gain mode, noise-profile setting, and Whisper model
              that transcribed it most accurately.
            </Typography>
            <Paper variant="outlined" sx={{ p: 2, fontStyle: 'italic' }}>
              {text || <CircularProgress size={20} aria-label="Loading passage" />}
            </Paper>
          </Box>
        )}

        {step === 'recording' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Alert severity="info">Recording… key up and read the passage now.</Alert>
            <Paper variant="outlined" sx={{ p: 2, fontStyle: 'italic' }}>{text}</Paper>
            <Typography variant="body2" color="text.secondary">
              Elapsed: {elapsedS}s
            </Typography>
          </Box>
        )}

        {step === 'analyzing' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 3 }}>
            <CircularProgress />
            <Typography variant="body2" color="text.secondary">
              {progress
                ? `Testing ${formatCombo(progress)} (${progress.index}/${progress.total})`
                : 'Analyzing…'}
            </Typography>
          </Box>
        )}

        {step === 'results' && results && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {applied && <Alert severity="success">Settings applied.</Alert>}
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Model</TableCell>
                  <TableCell>Gain</TableCell>
                  <TableCell>Noise profile</TableCell>
                  <TableCell>WER</TableCell>
                  <TableCell align="right">Apply</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {results.map((entry, i) => {
                  const isRecommended =
                    recommended !== null &&
                    entry.model === recommended.model &&
                    entry.gain_mode === recommended.gain_mode &&
                    entry.noise_profile === recommended.noise_profile;
                  return (
                    <TableRow
                      key={`${entry.model}-${entry.gain_mode}-${entry.noise_profile}-${i}`}
                      selected={isRecommended}
                    >
                      <TableCell>
                        {entry.model}
                        {isRecommended && (
                          <Typography component="span" variant="caption" color="primary" sx={{ ml: 1 }}>
                            Recommended
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>{entry.gain_mode}</TableCell>
                      <TableCell>{entry.noise_profile ? 'on' : 'off'}</TableCell>
                      <TableCell>{formatWer(entry.wer)}</TableCell>
                      <TableCell align="right">
                        <Button size="small" variant={isRecommended ? 'contained' : 'outlined'} onClick={() => handleApply(entry)}>
                          Apply
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        {step === 'intro' && (
          <>
            <Button onClick={onClose} variant="outlined">Cancel</Button>
            <Button onClick={handleStart} variant="contained" disabled={!text}>Start Recording</Button>
          </>
        )}
        {step === 'recording' && (
          <>
            <Button onClick={onClose} variant="outlined">Cancel</Button>
            <Button onClick={handleStop} variant="contained">Stop &amp; Analyze</Button>
          </>
        )}
        {step === 'analyzing' && (
          <Button onClick={onClose} variant="outlined">Close</Button>
        )}
        {step === 'results' && (
          <Button onClick={onClose} variant="outlined">Close</Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
