import type { NetSessionDetail, NetSessionRosterRow } from '../../types/ws';
import { netClock, netDate, netDateTime, formatDuration } from '../../netsessions/dates';
import { netTypeLabel } from '../../netsessions/netTypes';
import './NetRosterSheet.css';

/** What a printed row says about a station beyond the plain columns: a status
 *  that isn't the default, a caller the coordinator logged from the radio, and
 *  a round-table call that went unanswered. */
function notes(r: NetSessionRosterRow): string {
  const parts: string[] = [];
  if (r.status && r.status !== 'CheckedIn') parts.push(r.status);
  if (r.via === 'radio') parts.push('by radio');
  if (r.no_answer) parts.push('no answer when called');
  return parts.join(', ');
}

interface Props {
  session: NetSessionDetail;
  /** Injectable so the "printed at" line is testable. */
  now?: Date;
}

/**
 * A past net's roster as a sheet of paper.
 *
 * Screen-invisible by design (see NetRosterSheet.css) — PastNetsTab portals it
 * to <body> and `window.print()` does the rest. It prints the whole roster,
 * never the filtered or sorted table the operator happens to be looking at,
 * matching how CSV export and delete already treat the selected session.
 */
export function NetRosterSheet({ session, now = new Date() }: Props) {
  const roster = [...session.roster].sort((a, b) =>
    a.checkin_time.localeCompare(b.checkin_time)
  );
  const printed = `${now.toLocaleDateString('en-CA')} ${netClock(now.toISOString())}`;

  return (
    <div className="net-roster-sheet">
      <h1>
        {netTypeLabel(session.net_type)} net — {netDate(session.started_at)}
      </h1>
      <p className="sheet-meta" data-testid="sheet-meta">
        {netDateTime(session.started_at)} to {netDateTime(session.ended_at)}
        {' · '}
        {formatDuration(session.duration_seconds)}
        {' · '}
        {roster.length} check-in{roster.length === 1 ? '' : 's'}
      </p>

      {roster.length === 0 ? (
        <p>No check-ins recorded.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Callsign</th>
              <th scope="col">Name</th>
              <th scope="col">Location</th>
              <th scope="col">Check-in</th>
              <th scope="col">Traffic</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {roster.map((r, i) => (
              <tr key={`${r.callsign}-${r.checkin_time}`}>
                <td>{i + 1}</td>
                <td>{r.callsign}</td>
                <td>{r.name}</td>
                <td>{r.location}</td>
                <td>{netClock(r.checkin_time)}</td>
                <td>{r.traffic ?? ''}</td>
                <td data-testid="sheet-notes">{notes(r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="sheet-signoff">
        Prepared by ____________________________ Date ____________________
      </p>
      <p className="sheet-printed">Printed {printed}</p>
    </div>
  );
}
