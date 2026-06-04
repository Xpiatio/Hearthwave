import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CampaignIcon from '@mui/icons-material/Campaign';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteIcon from '@mui/icons-material/Delete';
import ReplayIcon from '@mui/icons-material/Replay';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import type { PluginProps } from '../../plugins';
import type { NCSEntry, NCSAlert } from '../../types/ws';

type TrafficLevel = 'Routine' | 'Priority' | 'Emergency' | 'General' | 'Short Term' | 'IN-n-Out';
type StationStatus = 'CheckedIn' | 'Standby' | 'LoggedOut';

const TRAFFIC_COLORS: Record<TrafficLevel, 'default' | 'warning' | 'error'> = {
  Routine: 'default',
  Priority: 'warning',
  Emergency: 'error',
  General: 'default',
  'Short Term': 'default',
  'IN-n-Out': 'default',
};

const STATUS_LABELS: Record<StationStatus, string> = {
  CheckedIn: '✓ In',
  Standby: 'Stby',
  LoggedOut: 'Out',
};

function playPcmAudio(b64: string, sampleRate: number): void {
  if (!b64) return;
  try {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;
    const ctx = new AudioContext({ sampleRate });
    const buf = ctx.createBuffer(1, float32.length, sampleRate);
    buf.getChannelData(0).set(float32);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    src.onended = () => ctx.close();
    src.start();
  } catch (e) {
    console.error('NCS replay playback error', e);
  }
}

function formatCheckinTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function NCSPanel({ send, lastMessage }: PluginProps) {
  const [active, setActive] = useState(false);
  const [roster, setRoster] = useState<NCSEntry[]>([]);
  const [alerts, setAlerts] = useState<NCSAlert[]>([]);
  const [callsignInput, setCallsignInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [locationInput, setLocationInput] = useState('');
  const [trafficInput, setTrafficInput] = useState<TrafficLevel>('Routine');
  const [breakBreakFlash, setBreakBreakFlash] = useState(false);
  const [journalSavedMsg, setJournalSavedMsg] = useState<string | null>(null);

  // Request current NCS state on mount
  useEffect(() => {
    send({ type: 'ncs_get_state' });
  }, [send]);

  // Handle server messages routed via lastMessage
  useEffect(() => {
    if (!lastMessage) return;
    switch (lastMessage.type) {
      case 'ncs_state':
        setActive(lastMessage.active);
        setRoster(lastMessage.roster);
        break;
      case 'ncs_roster_update':
        setRoster(lastMessage.roster);
        break;
      case 'ncs_alert':
        setAlerts((prev) => {
          if (prev.find((a) => a.id === lastMessage.id)) return prev;
          return [...prev, { id: lastMessage.id, event: lastMessage.event, headline: lastMessage.headline, zone: lastMessage.zone, severity: lastMessage.severity }];
        });
        break;
      case 'ncs_replay_audio':
        playPcmAudio(lastMessage.data, lastMessage.sample_rate);
        break;
      case 'ncs_break_break_ack':
        setBreakBreakFlash(true);
        setTimeout(() => setBreakBreakFlash(false), 3000);
        break;
      case 'ncs_journal_saved':
        setJournalSavedMsg(`Session journal saved.`);
        setTimeout(() => setJournalSavedMsg(null), 5000);
        break;
    }
  }, [lastMessage]);

  const handleStartNet = useCallback(() => send({ type: 'ncs_start' }), [send]);
  const handleEndNet = useCallback(() => send({ type: 'ncs_end' }), [send]);
  const handleBreakBreak = useCallback(() => send({ type: 'ncs_break_break' }), [send]);
  const handleReplay = useCallback(() => send({ type: 'ncs_get_replay' }), [send]);

  const handleCheckIn = useCallback(() => {
    const cs = callsignInput.trim().toUpperCase();
    if (!cs) return;
    send({ type: 'ncs_checkin', callsign: cs, traffic: trafficInput, name: nameInput.trim(), location: locationInput.trim() });
    setCallsignInput('');
    setNameInput('');
    setLocationInput('');
  }, [callsignInput, nameInput, locationInput, trafficInput, send]);

  const handleStatusToggle = useCallback((entry: NCSEntry) => {
    const next: StationStatus = entry.status === 'CheckedIn' ? 'Standby' : 'CheckedIn';
    send({ type: 'ncs_status_update', callsign: entry.callsign, name: entry.name ?? '', status: next });
  }, [send]);

  const handleRemove = useCallback((entry: NCSEntry) => {
    send({ type: 'ncs_remove', callsign: entry.callsign, name: entry.name ?? '' });
  }, [send]);

  return (
    <Paper elevation={0} square sx={{ borderBottom: 1, borderColor: 'divider', minWidth: 320 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1, borderBottom: 1, borderColor: 'divider' }}>
        <CampaignIcon fontSize="small" color={active ? 'error' : 'disabled'} />
        <Typography variant="subtitle2" sx={{ fontWeight: 700, flex: 1 }}>
          NET CONTROL STATION
        </Typography>
        <Chip
          label={active ? 'ACTIVE' : 'INACTIVE'}
          size="small"
          color={active ? 'error' : 'default'}
          sx={{ fontWeight: 700, letterSpacing: '0.05em' }}
        />
        <Tooltip title="Instant replay — last 15 seconds">
          <span>
            <IconButton size="small" onClick={handleReplay} disabled={!active} aria-label="Instant replay">
              <ReplayIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Button
          size="small"
          variant={active ? 'outlined' : 'contained'}
          color={active ? 'error' : 'primary'}
          onClick={active ? handleEndNet : handleStartNet}
          sx={{ minWidth: 80 }}
        >
          {active ? 'END NET' : 'START NET'}
        </Button>
      </Box>

      {/* NWS Alert banner */}
      {alerts.length > 0 && (
        <Box sx={{ bgcolor: 'error.dark', color: 'error.contrastText', px: 2, py: 0.75, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
          <WarningAmberIcon fontSize="small" sx={{ mt: 0.25, flexShrink: 0 }} />
          <Box sx={{ flex: 1 }}>
            {alerts.slice(-3).map((a) => (
              <Typography key={a.id} variant="caption" sx={{ display: 'block', lineHeight: 1.4 }}>
                <strong>{a.event}</strong> — {a.headline}
              </Typography>
            ))}
          </Box>
          <IconButton size="small" sx={{ color: 'inherit', p: 0.25 }} onClick={() => setAlerts([])} aria-label="Dismiss alerts">
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
      )}

      {/* Journal saved notice */}
      {journalSavedMsg && (
        <Box sx={{ bgcolor: 'success.dark', color: 'success.contrastText', px: 2, py: 0.5 }}>
          <Typography variant="caption">{journalSavedMsg}</Typography>
        </Box>
      )}

      {/* Check-in form */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, px: 2, py: 1, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Callsign"
            value={callsignInput}
            onChange={(e) => setCallsignInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCheckIn(); }}
            disabled={!active}
            slotProps={{ htmlInput: { style: { fontFamily: 'monospace', fontWeight: 700, width: 90 } } }}
            sx={{ width: 110 }}
            aria-label="Callsign to check in"
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel id="ncs-traffic-label">Traffic</InputLabel>
            <Select
              labelId="ncs-traffic-label"
              label="Traffic"
              value={trafficInput}
              onChange={(e) => setTrafficInput(e.target.value as TrafficLevel)}
              disabled={!active}
            >
              <MenuItem value="Routine">Routine</MenuItem>
              <MenuItem value="Priority">Priority</MenuItem>
              <MenuItem value="Emergency">Emergency</MenuItem>
              <MenuItem value="General">General</MenuItem>
              <MenuItem value="Short Term">Short Term</MenuItem>
              <MenuItem value="IN-n-Out">IN-n-Out</MenuItem>
            </Select>
          </FormControl>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Name"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            disabled={!active}
            sx={{ flex: 1 }}
            aria-label="Operator name"
          />
          <TextField
            size="small"
            placeholder="Location"
            value={locationInput}
            onChange={(e) => setLocationInput(e.target.value)}
            disabled={!active}
            sx={{ flex: 1 }}
            aria-label="Station location"
          />
          <Button
            variant="contained"
            size="small"
            onClick={handleCheckIn}
            disabled={!active || !callsignInput.trim()}
          >
            CHECK IN
          </Button>
        </Box>
      </Box>

      {/* Roster table */}
      {roster.length > 0 ? (
        <Box sx={{ overflowX: 'auto', maxHeight: 260, overflowY: 'auto' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700, py: 0.5 }}>Callsign</TableCell>
                <TableCell sx={{ fontWeight: 700, py: 0.5 }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700, py: 0.5 }}>Traffic</TableCell>
                <TableCell sx={{ fontWeight: 700, py: 0.5 }}>Time</TableCell>
                <TableCell sx={{ py: 0.5 }} />
              </TableRow>
            </TableHead>
            <TableBody>
              {roster.map((entry) => (
                <TableRow key={`${entry.callsign}|${entry.name ?? ''}`} hover>
                  <TableCell sx={{ fontFamily: 'monospace', fontWeight: 700, py: 0.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {entry.callsign}
                      {entry.verified && (
                        <Tooltip title="Verified contact">
                          <CheckCircleIcon fontSize="inherit" color="success" sx={{ fontSize: '0.9rem' }} />
                        </Tooltip>
                      )}
                    </Box>
                    {entry.name && (
                      <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>{entry.name}</Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }}>
                    <Tooltip title={`Click to toggle ${entry.status === 'CheckedIn' ? 'Standby' : 'CheckedIn'}`}>
                      <Chip
                        label={STATUS_LABELS[entry.status as StationStatus] ?? entry.status}
                        size="small"
                        color={entry.status === 'CheckedIn' ? 'success' : entry.status === 'Standby' ? 'warning' : 'default'}
                        onClick={() => handleStatusToggle(entry)}
                        clickable
                        sx={{ fontWeight: 700, minWidth: 48 }}
                      />
                    </Tooltip>
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }}>
                    <Chip
                      label={entry.traffic}
                      size="small"
                      color={TRAFFIC_COLORS[entry.traffic as TrafficLevel] ?? 'default'}
                    />
                  </TableCell>
                  <TableCell sx={{ py: 0.5, fontSize: '0.75rem', color: 'text.secondary' }}>
                    {formatCheckinTime(entry.checkin_time)}
                  </TableCell>
                  <TableCell sx={{ py: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleRemove(entry)}
                      aria-label={`Remove ${entry.callsign}`}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      ) : (
        active && (
          <Box sx={{ px: 2, py: 1.5, color: 'text.secondary' }}>
            <Typography variant="caption">No stations checked in. Type a callsign above.</Typography>
          </Box>
        )
      )}

      <Divider />

      {/* BREAK BREAK */}
      <Box sx={{ p: 1 }}>
        <Button
          variant="contained"
          color="error"
          fullWidth
          size="large"
          onClick={handleBreakBreak}
          disabled={!active}
          aria-label="BREAK BREAK — emergency interrupt, clears TX queue"
          sx={{
            fontWeight: 900,
            fontSize: '1rem',
            letterSpacing: '0.15em',
            py: 1,
            ...(breakBreakFlash && {
              animation: 'ncs-pulse 0.4s ease-in-out infinite alternate',
              '@keyframes ncs-pulse': {
                from: { opacity: 1 },
                to: { opacity: 0.5 },
              },
            }),
          }}
        >
          ■ BREAK BREAK ■
        </Button>
      </Box>
    </Paper>
  );
}
