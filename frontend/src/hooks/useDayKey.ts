import { useEffect, useState } from 'react';

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

function msUntilNextMidnight(now: Date): number {
  const next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0, 0);
  // Never schedule a zero/negative delay: a timer that fires immediately would
  // spin if the clock sits exactly on the boundary.
  return Math.max(next.getTime() - now.getTime(), 1000);
}

/** Local calendar-day key that changes at midnight, re-rendering the caller.
 *
 *  Timestamps render as "time only when it's today" (see utils/datetime), so a
 *  screen left open across midnight would keep yesterday's traffic looking like
 *  today's. Consumers don't need the returned value — reading it is enough to
 *  subscribe. Sleeps to the boundary rather than polling, so an idle kiosk
 *  wakes once a day. */
export function useDayKey(): string {
  const [key, setKey] = useState(() => dayKey(new Date()));

  useEffect(() => {
    const timer = setTimeout(() => setKey(dayKey(new Date())), msUntilNextMidnight(new Date()));
    return () => clearTimeout(timer);
    // Re-arms itself for the following midnight each time the key advances.
  }, [key]);

  return key;
}
