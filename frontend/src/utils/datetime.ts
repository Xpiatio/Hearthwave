/** Shared timestamp formatting for message-style surfaces (chat log, kiosk
 *  wall, neighborhood alerts/incidents, family "last OK").
 *
 *  The rule: today's traffic reads as a bare time, anything older carries a
 *  short date. That keeps the common case uncluttered — on the kiosk the
 *  caption is a single line — while making a scrollback that spans days
 *  readable. Because "today" changes at midnight on an always-on display,
 *  callers must format at render time from a raw ISO string rather than
 *  baking a label at ingest (see useDayKey). */

/** True when both dates fall on the same calendar day in the local zone. */
export function isSameLocalDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export interface FormatMessageTimeOptions {
  /** "Today" reference point. Defaults to the current clock. */
  now?: Date;
  /** Zero-padded hour ("09:15") vs. locale-natural ("9:15 AM"). Defaults to
   *  padded — the two hour styles already in the app differ, and quietly
   *  unifying them would restyle panels nobody asked to change. */
  padHour?: boolean;
}

/** Time-only when `iso` lands on the same local day as `now`, otherwise
 *  "Aug 5, 21:40". An absent or unparseable `iso` is treated as now, which
 *  preserves the old no-arg `formatTime()` behavior used for system messages. */
export function formatMessageTime(iso: string | undefined, opts: FormatMessageTimeOptions = {}): string {
  const { now = new Date(), padHour = true } = opts;
  const parsed = iso ? new Date(iso) : now;
  const d = Number.isNaN(parsed.getTime()) ? now : parsed;

  const time = d.toLocaleTimeString(undefined, {
    hour: padHour ? '2-digit' : 'numeric',
    minute: '2-digit',
  });
  if (isSameLocalDay(d, now)) return time;

  const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return `${date}, ${time}`;
}
