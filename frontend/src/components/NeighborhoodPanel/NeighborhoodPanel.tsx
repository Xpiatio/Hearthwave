import { useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, ButtonBase, Chip, IconButton, TextField, Tooltip, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import type { IncidentEntry, NeighborhoodAlertMsg, NeighborhoodRosterRow } from '../../types/ws';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';
import { nextNetLabel } from '../../neighborhood/schedule';
import { IncidentDialog } from './IncidentDialog';
import { IncidentLog } from './IncidentLog';
import { RosterList } from './RosterList';

export interface NeighborhoodPanelProps {
  roster: NeighborhoodRosterRow[];
  netActive: boolean;
  currentCall: string | null;
  incidents: IncidentEntry[];
  alerts: NeighborhoodAlertMsg[];
  netDay: string;
  netTime: string;
  isCoordinator: boolean;
  isKid: boolean;
  myUserId: string;
  onCheckin: () => void;
  onStatusChange: (status: 'checked_in' | 'standby') => void;
  onIncidentReport: (p: { category: string; description: string; location: string }) => void;
  incidentError: string | null;
  onStreetAlert: (message: string) => void;
  onStartNet: () => void;
  onEndNet: () => void;
  onCallNext: () => void;
  onNewRound: () => void;
  onGoHome: () => void;
}

const STREET_ALERT_MAX = 200;

function formatAlertTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** Resolve a raw current_call user_id (what the backend actually sends —
 *  see backend/neighborhood/net.py's call_next) to something a human can
 *  read: display name, falling back to callsign, falling back to nothing
 *  (never the raw user_id — "Current turn: dana-3f2a" is the bug this
 *  fixes) if the roster row can't be found or is missing both fields. */
function currentCallLabel(userId: string, roster: NeighborhoodRosterRow[]): string {
  const row = roster.find((r) => r.user_id === userId);
  return row?.name || row?.callsign || '';
}

/** Full-screen neighborhood activity: net status, a giant check-in button,
 *  street alerts, incident reporting/log, and (coordinator-only) net and
 *  round-table controls.
 *
 *  Rendered as a sibling of DesktopApp in App.tsx's shell ladder (mirroring
 *  FamilyPanel), so it owns its own Escape-to-home binding rather than
 *  relying on DesktopApp's — the two are never mounted at once. */
export function NeighborhoodPanel(props: NeighborhoodPanelProps) {
  useEscapeToHome(props.onGoHome);

  const [incidentOpen, setIncidentOpen] = useState(false);
  const [streetAlert, setStreetAlert] = useState('');

  // Tracks the most recent incidentError the user has already seen and
  // dismissed (via Cancel/backdrop close), so a stale error from a prior
  // visit never auto-reopens or redisplays. App.tsx only clears
  // incidentError on neighborhood_incident_sent — handleGoHome and
  // handleOpenActivity never do — so without this, leaving the panel after
  // a failed submit and coming back would auto-open a blank dialog showing
  // the old error again. Initializing to the mount-time value guards
  // against a stale error already present on first render.
  const dismissedErrorRef = useRef<string | null>(props.incidentError);

  // No dedicated "incident accepted" ack reaches this component (unlike
  // NCSPanel's spot-report flow, which closes on ncs_spot_report_sent) —
  // only incidentError. Submitting closes the dialog optimistically; if the
  // server rejects it, this reopens the dialog so the report and the error
  // are visible together. Only a *new*, undismissed error reopens it.
  useEffect(() => {
    if (props.incidentError && props.incidentError !== dismissedErrorRef.current) {
      setIncidentOpen(true);
    }
  }, [props.incidentError]);

  // The error is only worth showing while it hasn't been dismissed yet.
  const visibleIncidentError =
    props.incidentError !== null && props.incidentError !== dismissedErrorRef.current
      ? props.incidentError
      : null;

  const checkedIn = props.roster.some((r) => r.user_id === props.myUserId);
  const netLabel = nextNetLabel(props.netDay, props.netTime, new Date());
  // Kids never hold the coordinator grant in practice, but the panel
  // defends against it directly rather than trusting that invariant.
  const showCoordinatorSection = props.isCoordinator && !props.isKid;

  function handleIncidentSubmit(payload: { category: string; description: string; location: string }) {
    // A new attempt supersedes any dismissed error: App resets incidentError
    // to null on send, and clearing the ref here lets the rejection reopen
    // the dialog even when its text matches a previously dismissed error.
    dismissedErrorRef.current = null;
    props.onIncidentReport(payload);
    setIncidentOpen(false);
  }

  // Cancel/backdrop close (as opposed to the optimistic close on submit):
  // the user has now seen whatever error is currently showing, so record it
  // as dismissed until the next submit attempt resets the ref.
  function handleIncidentDialogClose() {
    dismissedErrorRef.current = props.incidentError;
    setIncidentOpen(false);
  }

  function handleSendStreetAlert() {
    const message = streetAlert.trim();
    if (!message) return;
    if (!window.confirm('Send this alert to everyone on the street?')) return;
    props.onStreetAlert(message);
    setStreetAlert('');
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', p: { xs: 2, md: 4 }, gap: 3 }}>
      <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Tooltip title="Back to home">
          <IconButton aria-label="Back to home" onClick={props.onGoHome}>
            <ArrowBackIcon />
          </IconButton>
        </Tooltip>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Neighborhood
        </Typography>
        <Chip
          size="small"
          color={props.netActive ? 'success' : 'default'}
          label={props.netActive ? 'Net running' : 'No net right now'}
        />
        {!props.netActive && netLabel && (
          <Typography variant="body2" color="text.secondary">{netLabel}</Typography>
        )}
      </Box>

      {props.alerts.length > 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {props.alerts.map((a) => (
            <Alert key={a.id} severity="warning">
              {a.message} — {a.issued_by}, {formatAlertTime(a.ts)}
            </Alert>
          ))}
        </Box>
      )}

      <ButtonBase
        onClick={props.onCheckin}
        disabled={checkedIn}
        aria-label={checkedIn ? "You're checked in ✓" : 'Check in'}
        sx={{
          minHeight: 96,
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 2,
          fontSize: '1.4rem',
          fontWeight: 700,
          gap: 1.5,
          bgcolor: checkedIn ? 'success.main' : 'primary.main',
          color: checkedIn ? 'success.contrastText' : 'primary.contrastText',
        }}
      >
        {checkedIn ? "You're checked in ✓" : 'Check in'}
      </ButtonBase>

      {!props.isKid && (
        <Button
          variant="outlined"
          onClick={() => setIncidentOpen(true)}
          sx={{ alignSelf: 'flex-start', minHeight: 56 }}
        >
          Report an incident
        </Button>
      )}

      <RosterList
        roster={props.roster}
        currentCall={props.currentCall}
        myUserId={props.myUserId}
        onStatusChange={props.onStatusChange}
      />

      <IncidentLog incidents={props.incidents} />

      {showCoordinatorSection && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Coordinator tools
          </Typography>

          <Typography variant="body2" color="text.secondary">
            {props.currentCall
              ? `Current turn: ${currentCallLabel(props.currentCall, props.roster)}`
              : 'No one called yet this round.'}
          </Typography>

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              onClick={props.netActive ? props.onEndNet : props.onStartNet}
            >
              {props.netActive ? 'End net' : 'Start net'}
            </Button>
            <Button variant="outlined" onClick={props.onCallNext} disabled={!props.netActive}>
              Call next neighbor
            </Button>
            <Button variant="outlined" onClick={props.onNewRound} disabled={!props.netActive}>
              New round
            </Button>
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <TextField
              size="small"
              label="Street alert message"
              value={streetAlert}
              onChange={(e) => setStreetAlert(e.target.value.slice(0, STREET_ALERT_MAX))}
              placeholder="e.g. Power out on Maple St, crews on the way"
              helperText={`${streetAlert.length}/${STREET_ALERT_MAX}`}
              slotProps={{ htmlInput: { maxLength: STREET_ALERT_MAX } }}
            />
            <Button
              variant="contained"
              color="warning"
              onClick={handleSendStreetAlert}
              disabled={!streetAlert.trim()}
              sx={{ alignSelf: 'flex-start' }}
            >
              Send street alert
            </Button>
          </Box>
        </Box>
      )}

      <IncidentDialog
        open={incidentOpen}
        error={visibleIncidentError}
        onClose={handleIncidentDialogClose}
        onSubmit={handleIncidentSubmit}
      />
    </Box>
  );
}
