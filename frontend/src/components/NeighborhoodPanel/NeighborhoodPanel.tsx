import { useState } from 'react';
import { Alert, Box, Button, ButtonBase, Chip, IconButton, TextField, Tooltip, Typography, useMediaQuery } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';
import { nextNetLabel } from '../../neighborhood/schedule';
import { IncidentDialog } from './IncidentDialog';
import { IncidentLog } from './IncidentLog';
import { RosterList } from './RosterList';
import { RadioCheckinForm } from './RadioCheckinForm';
import { ConfirmDialog } from '../ConfirmDialog';
import { CoordinatorDashboard } from './CoordinatorDashboard';
import { useIncidentDialog } from './useIncidentDialog';
import { currentCallLabel, formatAlertTime } from './shared';
import type { NeighborhoodPanelProps } from './shared';

export type { NeighborhoodPanelProps } from './shared';
export { currentCallLabel } from './shared';

const STREET_ALERT_MAX = 200;

/** Full-screen neighborhood activity: net status, a giant check-in button,
 *  street alerts, incident reporting/log, and (coordinator-only) net and
 *  round-table controls.
 *
 *  A pure switch: on a wide screen (≥1200px), a coordinator who isn't a
 *  kid, and a session the App has wired up for TX (`messages !== undefined`)
 *  get CoordinatorDashboard's single-viewport ops console instead of the
 *  stacked view below. Kept as the only hook here (`useMediaQuery`) so the
 *  two branches can be genuinely different component types — each owns its
 *  own hooks (including its own Escape-to-home binding) without any risk of
 *  hook-order mismatches across renders when the viewport crosses the
 *  breakpoint. */
export function NeighborhoodPanel(props: NeighborhoodPanelProps) {
  const wideViewport = useMediaQuery('(min-width:1200px)');
  // Kids never hold the coordinator grant in practice, but the panel
  // defends against it directly rather than trusting that invariant.
  const showCoordinatorSection = props.isCoordinator && !props.isKid;

  if (showCoordinatorSection && wideViewport && props.messages !== undefined) {
    return (
      <CoordinatorDashboard
        {...props}
        messages={props.messages}
        transmitting={props.transmitting ?? false}
        showCallsignChips={props.showCallsignChips ?? false}
        onSendMessage={props.onSendMessage ?? (() => {})}
        onChat={props.onChat ?? (() => {})}
        onStandaloneId={props.onStandaloneId ?? (() => {})}
        txComposition={props.txComposition ?? null}
        onTxAbort={props.onTxAbort}
      />
    );
  }

  return <StackedNeighborhoodView {...props} showCoordinatorSection={showCoordinatorSection} />;
}

interface StackedNeighborhoodViewProps extends NeighborhoodPanelProps {
  showCoordinatorSection: boolean;
}

/** The original full-page layout: check-in button, roster, incident log,
 *  and (coordinator-only) net/round-table controls stacked in a single
 *  vertical scroll. Serves narrow screens, participants, and kids — anyone
 *  the wide-screen switch above doesn't route to CoordinatorDashboard.
 *
 *  Rendered as a sibling of DesktopApp in App.tsx's shell ladder (mirroring
 *  FamilyPanel), so it owns its own Escape-to-home binding rather than
 *  relying on DesktopApp's — the two are never mounted at once. */
function StackedNeighborhoodView(props: StackedNeighborhoodViewProps) {
  useEscapeToHome(props.onGoHome);

  const [streetAlert, setStreetAlert] = useState('');
  const [alertConfirmOpen, setAlertConfirmOpen] = useState(false);
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
  const showCoordinatorSection = props.showCoordinatorSection;

  function requestSendStreetAlert() {
    if (!streetAlert.trim()) return;
    setAlertConfirmOpen(true);
  }

  function confirmSendStreetAlert() {
    const message = streetAlert.trim();
    if (!message) return;
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
        onClear={props.isAdmin ? () => setClearCheckinsConfirmOpen(true) : undefined}
        isCoordinator={showCoordinatorSection}
        onStationStatusChange={props.onStationStatusChange}
        onRemoveStation={props.onRemoveStation}
        onCallStation={showCoordinatorSection && props.netActive ? props.onCallStation : undefined}
        onNoAnswer={showCoordinatorSection ? props.onNoAnswer : undefined}
      />

      <IncidentLog
        incidents={props.incidents}
        onClear={props.isAdmin ? () => setClearIncidentsConfirmOpen(true) : undefined}
      />

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

          <RadioCheckinForm contacts={props.contacts} onCheckin={props.onRadioCheckin} />

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
              onClick={requestSendStreetAlert}
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

      <ConfirmDialog
        open={alertConfirmOpen}
        title="Send this alert to everyone?"
        body={streetAlert.trim()}
        confirmLabel="Yes, send the alert"
        destructive
        onConfirm={confirmSendStreetAlert}
        onClose={() => setAlertConfirmOpen(false)}
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
