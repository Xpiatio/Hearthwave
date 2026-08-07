/**
 * Presentation helpers for heard-station positions.
 *
 * Separate from the components so the map and the list can share them without
 * the map importing a table component's module. The server resolves distance,
 * bearing and age; nothing here recomputes geography.
 */

/** Human-readable source names; an unknown plugin id is shown as-is. */
const SOURCE_LABELS: Record<string, string> = {
  meshtastic: 'Meshtastic',
  meshcore: 'MeshCore',
  aprs_rf: 'APRS',
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

/** Distance in the unit the operator reads on the air. */
export function formatDistance(km: number | null, units: 'mi' | 'km'): string {
  if (km === null) return '—';
  const value = units === 'mi' ? km * 0.621371 : km;
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units}`;
}

/** Coarse age. Anything past a day is "1d+" — the TTL drops it soon after. */
export function formatAge(seconds: number): string {
  if (seconds < 60) return 'now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return '1d+';
}

/** Spoken-friendly bearing for the screen reader, e.g. "north-northeast". */
export const COMPASS_WORDS: Record<string, string> = {
  N: 'north', NNE: 'north-northeast', NE: 'northeast', ENE: 'east-northeast',
  E: 'east', ESE: 'east-southeast', SE: 'southeast', SSE: 'south-southeast',
  S: 'south', SSW: 'south-southwest', SW: 'southwest', WSW: 'west-southwest',
  W: 'west', WNW: 'west-northwest', NW: 'northwest', NNW: 'north-northwest',
};
