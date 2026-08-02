import { useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, Chip, IconButton, Paper, Tooltip, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import type { TxComposition } from '../../plugins';
import { ChatDisplay } from '../ChatDisplay/ChatDisplay';
import { MessageInput } from '../MessageInput/MessageInput';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';
import { nextNetLabel } from '../../neighborhood/schedule';
import { RosterList } from './RosterList';
import { IncidentLog } from './IncidentLog';
import { IncidentDialog } from './IncidentDialog';
import { RadioCheckinForm } from './RadioCheckinForm';
import { StreetAlertDialog } from './StreetAlertDialog';
import { ConfirmDialog } from '../ConfirmDialog';
import { currentCallLabel } from './NeighborhoodPanel';
import type { NeighborhoodPanelProps } from './NeighborhoodPanel';

export interface CoordinatorDashboardProps extends NeighborhoodPanelProps {
  messages: ChatEntry[];
  transmitting: boolean;
  showCallsignChips: boolean;
  onSendMessage: (text: string, targetCall: string, targetName: string) => void;
  onChat: (text: string) => void;
  onStandaloneId: () => void;
  txComposition: TxComposition | null;
}

function formatAlertTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** Single-viewport net-ops console for a coordinator on a desktop: radio
 *  traffic and check-in entry on the left, roster and incidents on the
 *  right, net controls in a persistent command bar. The stacked
 *  NeighborhoodPanel remains the participant/narrow-screen view; the
 *  ≥1200px switch lives in NeighborhoodPanel. */
export function CoordinatorDashboard(props: CoordinatorDashboardProps) {
  useEscapeToHome(props.onGoHome);

  const [incidentOpen, setIncidentOpen] = useState(false);
  const [streetAlertOpen, setStreetAlertOpen] = useState(false);
  const [clearCheckinsConfirmOpen, setClearCheckinsConfirmOpen] = useState(false);
  const [clearIncidentsConfirmOpen, setClearIncidentsConfirmOpen] = useState(false);

  // Tracks the most recent incidentError the user has already seen and
  // dismissed (via Cancel/backdrop close), so a stale error from a prior
  // visit never auto-reopens or redisplays. Mirrors NeighborhoodPanel's
  // dismissed-error ref pattern verbatim (see NeighborhoodPanel.tsx).
  const dismissedErrorRef = useRef<string | null>(props.incidentError);

  useEffect(() => {
    if (props.incidentError && props.incidentError !== dismissedErrorRef.current) {
      setIncidentOpen(true);
    }
  }, [props.incidentError]);

  const visibleIncidentError =
    props.incidentError !== null && props.incidentError !== dismissedErrorRef.current
      ? props.incidentError
      : null;

  function handleIncidentSubmit(payload: { category: string; description: string; location: string }) {
    dismissedErrorRef.current = null;
    props.onIncidentReport(payload);
    setIncidentOpen(false);
  }

  function handleIncidentDialogClose() {
    dismissedErrorRef.current = props.incidentError;
    setIncidentOpen(false);
  }

  const checkedIn = props.roster.some((r) => r.user_id === props.myUserId);
  const netLabel = nextNetLabel(props.netDay, props.netTime, new Date());

  return (
    <Box sx={{ height: '100vh', display: 'grid', gridTemplateRows: 'auto auto 1fr', gap: 1.5, p: 2, boxSizing: 'border-box', overflow: 'hidden' }}>
      <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        <Tooltip title="Back to home">
          <IconButton aria-label="Back to home" onClick={props.onGoHome}>
            <ArrowBackIcon />
          </IconButton>
        </Tooltip>
        <Typography variant="h6">Neighborhood</Typography>
        <Chip
          size="small"
          color={props.netActive ? 'success' : 'default'}
          label={props.netActive ? 'Net running' : 'No net right now'}
        />
        {!props.netActive && netLabel && (
          <Typography variant="body2" color="text.secondary">{netLabel}</Typography>
        )}
        <Button variant="contained" size="small" onClick={props.netActive ? props.onEndNet : props.onStartNet}>
          {props.netActive ? 'End net' : 'Start net'}
        </Button>
        <Button variant="outlined" size="small" onClick={props.onCallNext} disabled={!props.netActive}>
          Call next neighbor
        </Button>
        <Button variant="outlined" size="small" onClick={props.onNewRound} disabled={!props.netActive}>
          New round
        </Button>
        <Button variant="outlined" size="small" color="warning" onClick={() => setStreetAlertOpen(true)}>
          Street alert…
        </Button>
        <Typography variant="body2" color="text.secondary">
          {props.currentCall
            ? `Current turn: ${currentCallLabel(props.currentCall, props.roster)}`
            : 'No one called yet this round.'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {props.roster.length} checked in
        </Typography>
        <Chip
          component="button"
          clickable={!checkedIn}
          disabled={checkedIn}
          color={checkedIn ? 'success' : 'primary'}
          label={checkedIn ? "You're checked in ✓" : 'Check in'}
          onClick={checkedIn ? undefined : props.onCheckin}
          sx={{ ml: 'auto' }}
        />
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

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, minHeight: 0 }}>
        {/* Left: transcript over TX over check-in form */}
        <Box sx={{ display: 'grid', gridTemplateRows: '1fr auto auto', gap: 1, minHeight: 0 }}>
          <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1 }}>
            <ChatDisplay entries={props.messages} contacts={props.contacts} showCallsignChips={props.showCallsignChips} />
          </Paper>
          <MessageInput
            transmitting={props.transmitting}
            contacts={props.contacts}
            onSend={props.onSendMessage}
            onChat={props.onChat}
            onStandaloneId={props.onStandaloneId}
            maxBytes={props.txComposition?.maxBytes}
            composeHint={props.txComposition?.hint}
          />
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <RadioCheckinForm contacts={props.contacts} onCheckin={props.onRadioCheckin} />
          </Paper>
        </Box>

        {/* Right: roster over incidents */}
        <Box sx={{ display: 'grid', gridTemplateRows: '1.6fr 1fr', gap: 1.5, minHeight: 0 }}>
          <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1.5 }}>
            <RosterList
              roster={props.roster}
              currentCall={props.currentCall}
              myUserId={props.myUserId}
              onStatusChange={props.onStatusChange}
              onClear={props.isAdmin ? () => setClearCheckinsConfirmOpen(true) : undefined}
              isCoordinator
              onStationStatusChange={props.onStationStatusChange}
              onRemoveStation={props.onRemoveStation}
              onCallStation={props.onCallStation}
              onNoAnswer={props.onNoAnswer}
            />
          </Paper>
          <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button size="small" variant="outlined" onClick={() => setIncidentOpen(true)}>
                Report an incident
              </Button>
            </Box>
            <IncidentLog
              incidents={props.incidents}
              onClear={props.isAdmin ? () => setClearIncidentsConfirmOpen(true) : undefined}
            />
          </Paper>
        </Box>
      </Box>

      <IncidentDialog
        open={incidentOpen}
        error={visibleIncidentError}
        onClose={handleIncidentDialogClose}
        onSubmit={handleIncidentSubmit}
      />

      <StreetAlertDialog
        open={streetAlertOpen}
        onClose={() => setStreetAlertOpen(false)}
        onSend={props.onStreetAlert}
      />

      <ConfirmDialog
        open={clearCheckinsConfirmOpen}
        title="Clear everyone off the check-in list?"
        body={
          props.netActive
            ? "Everyone will have to check in again. The net keeps running."
            : "Everyone will have to check in again."
        }
        confirmLabel="Yes, clear the check-ins"
        destructive
        onConfirm={props.onClearCheckins}
        onClose={() => setClearCheckinsConfirmOpen(false)}
      />

      <ConfirmDialog
        open={clearIncidentsConfirmOpen}
        title="Clear the incident log?"
        body="The reports are saved to a journal entry first, then removed from this list."
        confirmLabel="Yes, clear the log"
        destructive
        onConfirm={props.onClearIncidents}
        onClose={() => setClearIncidentsConfirmOpen(false)}
      />
    </Box>
  );
}
