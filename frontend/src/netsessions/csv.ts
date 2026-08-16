import type { NetSessionDetail, NetSessionSummary } from '../types/ws';
import { netDate } from './dates';

/** Leading characters that make Excel (and Sheets, and LibreOffice) read a
 *  cell as a formula rather than text. */
const FORMULA_LEAD = /^[=+\-@\t\r]/;

/** One CSV cell: always quoted, embedded quotes doubled. Shared with the
 *  ICS-214 export so both writers escape a field the same way.
 *
 *  A cell whose first character could start a formula gets a leading
 *  apostrophe — the spreadsheet's own "this is text" marker, which it hides
 *  on display. Quoting alone does not save us here: Excel strips the quotes
 *  and *then* evaluates the cell, so a check-in name of `=WEBSERVICE(...)`
 *  would run when whoever we handed the export to opened it. Names,
 *  locations and traffic notes are free text from a check-in, so that input
 *  is not ours to trust. */
export function quote(value: string | number | null): string {
  const raw = String(value ?? '');
  const safe = FORMULA_LEAD.test(raw) ? `'${raw}` : raw;
  return `"${safe.replace(/"/g, '""')}"`;
}

/** One session's roster: header plus one row per check-in. */
export function sessionToCsv(session: NetSessionDetail): string {
  const header = 'callsign,name,location,status,traffic,checkin_time,via,no_answer';
  const rows = session.roster.map((r) =>
    [
      r.callsign, r.name, r.location, r.status, r.traffic ?? '', r.checkin_time,
      r.via ?? '', r.no_answer ? 'yes' : '',
    ]
      .map(quote)
      .join(',')
  );
  return [header, ...rows].join('\n');
}

/** Every net: header plus one row per station per net. */
export function allSessionsToCsv(sessions: NetSessionSummary[]): string {
  const header = 'net_id,net_type,net_date,callsign,name';
  const rows = sessions.flatMap((s) =>
    s.stations.map((station) =>
      [s.id, s.net_type, netDate(s.started_at), station.callsign, station.name]
        .map(quote)
        .join(',')
    )
  );
  return [header, ...rows].join('\n');
}
