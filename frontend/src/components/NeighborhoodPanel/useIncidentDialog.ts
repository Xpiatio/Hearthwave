import { useEffect, useRef, useState } from 'react';

export interface IncidentReportPayload {
  category: string;
  description: string;
  location: string;
}

export interface UseIncidentDialogResult {
  incidentOpen: boolean;
  setIncidentOpen: (open: boolean) => void;
  visibleIncidentError: string | null;
  handleIncidentSubmit: (payload: IncidentReportPayload) => void;
  handleIncidentDialogClose: () => void;
}

/**
 * Incident-dialog open/error state, shared verbatim between
 * NeighborhoodPanel's stacked view and CoordinatorDashboard (previously
 * duplicated near-identically between the two — see task-8 audit).
 *
 * Tracks the most recent incidentError the caller has already seen and
 * dismissed (via Cancel/backdrop close), so a stale error from a prior
 * visit never auto-reopens or redisplays. App.tsx only clears
 * incidentError on neighborhood_incident_sent — handleGoHome and
 * handleOpenActivity never do — so without this, leaving the panel after
 * a failed submit and coming back would auto-open a blank dialog showing
 * the old error again. Initializing to the mount-time value guards
 * against a stale error already present on first render.
 *
 * No dedicated "incident accepted" ack reaches either component (unlike
 * NCSPanel's spot-report flow, which closes on ncs_spot_report_sent) —
 * only incidentError. Submitting closes the dialog optimistically; if the
 * server rejects it, this reopens the dialog so the report and the error
 * are visible together. Only a *new*, undismissed error reopens it.
 */
export function useIncidentDialog(
  incidentError: string | null,
  onIncidentReport: (payload: IncidentReportPayload) => void,
): UseIncidentDialogResult {
  const [incidentOpen, setIncidentOpen] = useState(false);

  const dismissedErrorRef = useRef<string | null>(incidentError);

  useEffect(() => {
    if (incidentError && incidentError !== dismissedErrorRef.current) {
      setIncidentOpen(true);
    }
  }, [incidentError]);

  // The error is only worth showing while it hasn't been dismissed yet.
  const visibleIncidentError =
    incidentError !== null && incidentError !== dismissedErrorRef.current
      ? incidentError
      : null;

  function handleIncidentSubmit(payload: IncidentReportPayload) {
    // A new attempt supersedes any dismissed error: App resets incidentError
    // to null on send, and clearing the ref here lets the rejection reopen
    // the dialog even when its text matches a previously dismissed error.
    dismissedErrorRef.current = null;
    onIncidentReport(payload);
    setIncidentOpen(false);
  }

  // Cancel/backdrop close (as opposed to the optimistic close on submit):
  // the user has now seen whatever error is currently showing, so record it
  // as dismissed until the next submit attempt resets the ref.
  function handleIncidentDialogClose() {
    dismissedErrorRef.current = incidentError;
    setIncidentOpen(false);
  }

  return { incidentOpen, setIncidentOpen, visibleIncidentError, handleIncidentSubmit, handleIncidentDialogClose };
}
