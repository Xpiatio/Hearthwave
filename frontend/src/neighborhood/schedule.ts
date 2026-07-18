// Pure "next net" label helper for the Neighborhood activity's admin-set
// schedule (net_day/net_time from server config). The label is intentionally
// date-free — it names the day-of-week and time-of-day the net recurs on, not
// a specific calendar date — so `now` only exists for callers who want to gate
// display (e.g. hide the label once far past); it does not change the text.

const DAY_LABELS: Record<string, string> = {
  mon: 'Mon',
  tue: 'Tue',
  wed: 'Wed',
  thu: 'Thu',
  fri: 'Fri',
  sat: 'Sat',
  sun: 'Sun',
};

const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

export function nextNetLabel(day: string, time: string, _now: Date): string {
  const dayLabel = DAY_LABELS[(day || '').trim().toLowerCase()];
  if (!dayLabel) return '';

  const match = TIME_RE.exec((time || '').trim());
  if (!match) return '';

  let hours = Number(match[1]);
  const minutes = match[2];
  const period = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12;

  return `Net ${dayLabel} ${hours}:${minutes} ${period}`;
}
