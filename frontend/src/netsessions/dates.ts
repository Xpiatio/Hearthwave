/**
 * Local-calendar-day label for a net session timestamp.
 *
 * `started_at`/`ended_at` are UTC ISO-8601 strings. Slicing the first 10
 * characters reads the *UTC* calendar date, which mislabels an evening net
 * with tomorrow's date for anyone west of UTC (and yesterday's for anyone
 * east of it). Parsing through `Date` and formatting with the viewer's own
 * timezone gives the date the operator actually experienced the net on.
 *
 * `en-CA` renders as YYYY-MM-DD, matching the previous UTC-slice format so
 * existing sort order / column width assumptions still hold.
 */
export function netDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString('en-CA');
}

/**
 * Local date *and* clock time for a net session timestamp.
 *
 * The start→end caption is the one place the time of day carries the
 * information ("7:02 PM to 7:48 PM"), so `netDate` alone would render the
 * same date twice. Same timezone reasoning as `netDate`; the viewer's own
 * locale formats it, since this string is read, not sorted or parsed.
 */
export function netDateTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
