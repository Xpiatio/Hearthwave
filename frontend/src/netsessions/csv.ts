import type { NetSessionDetail, NetSessionSummary } from '../types/ws';
import { netDate } from './dates';

function quote(value: string | number | null): string {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
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
