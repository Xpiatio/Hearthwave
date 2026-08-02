import { useState } from 'react';
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
import { useIncidentDialog } from './useIncidentDialog';
import { currentCallLabel, formatAlertTime } from './shared';
import type { NeighborhoodPanelProps } from './shared';

export interface CoordinatorDashboardProps extends NeighborhoodPanelProps {
  messages: ChatEntry[];
  transmitting: boolean;
  showCallsignChips: boolean;
  onSendMessage: (text: string, targetCall: string, targetName: string) => void;
  onChat: (text: string) => void;
  onStandaloneId: () => void;
  txComposition: TxComposition | null;
}

/** Single-viewport net-ops console for a coordinator on a desktop: radio
 *  traffic and check-in entry on the left, roster and incidents on the
 *  right, net controls in a persistent command bar. The stacked
 *  NeighborhoodPanel remains the participant/narrow-screen view; the
 *  ≥1200px switch lives in NeighborhoodPanel. */
export function CoordinatorDashboard(props: CoordinatorDashboardProps) {
  useEscapeToHome(props.onGoHome);

  const [streetAlertOpen, setStreetAlertOpen] = useState(false);
  const [clearCheckinsConfirmOpen, setClearCheckinsConfirmOpen] = useState(false);
  const [clearIncidentsConfirmOpen, setClearIncidentsConfirmOpen] = useState(false);

  const {
    incidentOpen,
    setIncidentOpen,
    visibleIncidentError,
    handleIncidentSubmit,
    handleIncidentDialogClose,
  } = useIncidentDialog(props.incidentError, props.onIncidentReport);

  const checkedIn = props.roster.some((r) => r.user_id === props.myUserId);
  const netLabel = nextNetLabel(props.netDay, props.netTime, new Date());
  // Only the no-alerts case (the default) can drop the alerts row from the
  // template entirely; when it renders `false` with a static three-row
  // template, grid auto-placement shoves the main split into the middle
  // `auto` row and leaves the `1fr` row empty, clipping MessageInput and
  // RadioCheckinForm below the fold. See task-7 review finding 1.
  const gridTemplateRows = props.alerts.length > 0 ? 'auto auto 1fr' : 'auto 1fr';
  // A listen-only coordinator session (mirrors DesktopApp's
  // `!listenOnly && !isKid` gate) drops the transmit box from the left
  // column — everything else in the dashboard (roster, incidents, radio
  // check-in) stays, since none of that is a transmit action.
  const showMessageInput = !props.listenOnly;
  const leftColumnRows = showMessageInput ? '1fr auto auto' : '1fr auto';
  // isKid is already excluded by the gate that routes here (NeighborhoodPanel
  // only ever mounts this component when isCoordinator && !isKid), but this
  // component doesn't rely on that invariant holding for every caller (e.g.
  // its own standalone tests) — it re-derives the real value directly, the
  // same way NeighborhoodPanel's stacked view does.
  const isRosterCoordinator = props.isCoordinator && !props.isKid;

  return (
    <Box sx={{ height: '100vh', display: 'grid', gridTemplateRows, gap: 1.5, p: 2, boxSizing: 'border-box', overflow: 'hidden' }}>
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
        {/* No component/clickable override: MUI only renders Chip as a
            focusable ButtonBase when onClick is present, so once
            checked in (onClick undefined) it falls back to a plain,
            non-interactive <div> — genuinely inert, not just visually
            "disabled". `disabled` is kept only for the dimmed styling. */}
        <Chip
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
        {/* Left: transcript over TX (when not listen-only) over check-in form */}
        <Box sx={{ display: 'grid', gridTemplateRows: leftColumnRows, gap: 1, minHeight: 0 }}>
          <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'hidden', display: 'flex', p: 1 }}>
            <ChatDisplay entries={props.messages} contacts={props.contacts} showCallsignChips={props.showCallsignChips} />
          </Paper>
          {showMessageInput && (
            <MessageInput
              transmitting={props.transmitting}
              contacts={props.contacts}
              onSend={props.onSendMessage}
              onChat={props.onChat}
              onStandaloneId={props.onStandaloneId}
              maxBytes={props.txComposition?.maxBytes}
              composeHint={props.txComposition?.hint}
            />
          )}
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
              isCoordinator={isRosterCoordinator}
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
