import type { NetSessionDetail, NetSessionRosterRow } from '../types/ws';
import { quote } from './csv';
import { netTypeLabel } from './netTypes';

/** The ICS-214 boxes that have no home in a net session record — an incident
 *  name, who prepared the form, and under what agency. The operator supplies
 *  these at export time. */
export interface Ics214Header {
  incidentName: string;
  preparedByName: string;
  preparedByPosition: string;
  homeAgency: string;
}

/** `YYYY-MM-DD HH:MM` in the viewer's own timezone. An activity log records
 *  wall-clock local time (that's what a responder writes on the paper form),
 *  and 24-hour is the form's convention — hence `en-GB` for the clock rather
 *  than the viewer's locale, which may render 12-hour. */
function stampDate(d: Date): string {
  const date = d.toLocaleDateString('en-CA');
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

/** `stampDate` for a UTC ISO-8601 string; blank in, blank out. */
function stamp(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : stampDate(d);
}

/** One check-in as an ICS-214 "Notable Activities" entry. The roster's
 *  columns have no counterpart on the form, so everything worth keeping —
 *  traffic, a non-default status, the radio/self distinction, an unanswered
 *  round-table call — folds into the activity text. */
function activityText(r: NetSessionRosterRow): string {
  const parts = [`Check-in: ${r.callsign}`];
  if (r.name) parts.push(r.name);
  if (r.location) parts.push(r.location);
  if (r.traffic) parts.push(`${r.traffic} traffic`);
  if (r.status && r.status !== 'CheckedIn') parts.push(`status: ${r.status}`);
  if (r.via) parts.push(`via ${r.via}`);
  const line = parts.join(' — ');
  return r.no_answer ? `${line} (no answer when called)` : line;
}

/**
 * One session as an ICS-214 Activity Log, in the paper form's numbered-box
 * order rather than as a flat table — the point is a file an ARES/RACES
 * section can print or paste into the real form, not one a script can parse.
 *
 * The activity log is synthesized: the session's own `transcript` field holds
 * roster lines, not timed events, so the entries here are the net opening,
 * each check-in at its `checkin_time`, and the net closing.
 *
 * `now` is injectable so the box 8 sign-off timestamp is testable.
 */
export function sessionToIcs214Csv(
  session: NetSessionDetail,
  header: Ics214Header,
  now: Date = new Date(),
): string {
  const roster = [...session.roster].sort((a, b) =>
    a.checkin_time.localeCompare(b.checkin_time)
  );
  const count = roster.length;

  const rows: string[] = [
    'ICS 214,ACTIVITY LOG',
    `1. Incident Name,${quote(header.incidentName)}`,
    '2. Operational Period,' +
      `Date/Time From,${quote(stamp(session.started_at))},` +
      `Date/Time To,${quote(stamp(session.ended_at))}`,
    `3. Name,${quote(header.preparedByName)}`,
    `4. ICS Position,${quote(header.preparedByPosition)}`,
    `5. Home Agency (and Unit),${quote(header.homeAgency)}`,
    '',
    '6. Resources Assigned',
    'Name,ICS Position,Home Agency (and Unit)',
  ];

  for (const r of roster) {
    const name = r.name ? `${r.callsign} — ${r.name}` : r.callsign;
    rows.push([name, 'Net Participant', ''].map(quote).join(','));
  }

  rows.push('', '7. Activity Log', 'Date/Time,Notable Activities');
  if (session.started_at) {
    const opened = `Net opened (${netTypeLabel(session.net_type)})`;
    rows.push([stamp(session.started_at), opened].map(quote).join(','));
  }
  for (const r of roster) {
    rows.push([stamp(r.checkin_time), activityText(r)].map(quote).join(','));
  }
  if (session.ended_at) {
    const closed = `Net closed — ${count} check-in${count === 1 ? '' : 's'}`;
    rows.push([stamp(session.ended_at), closed].map(quote).join(','));
  }

  rows.push(
    '',
    '8. Prepared by,Name,Position/Title,Signature,Date/Time',
    ',' +
      [header.preparedByName, header.preparedByPosition, '', stampDate(now)]
        .map(quote)
        .join(','),
  );

  return rows.join('\n');
}
