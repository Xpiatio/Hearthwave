/** Roster density: how tightly the neighborhood board packs its rows.
 *
 *  The checked-in-neighbors list used to be one stacked column, so a net with
 *  twenty people meant scrolling past the neighbor you were looking for. Same
 *  treatment as the family presence board (family/density.ts): pick a tier
 *  from the head count, feed the grid's column bounds from it, and scale the
 *  card's typography and spacing to match.
 *
 *  Two things differ from the family tiers. The thresholds sit higher — a net
 *  of six is still a small net, where a household of six is already crowded.
 *  And every tier's min column is wider, because a roster row carries name,
 *  callsign, location, status and a self-toggle button, not an emoji and a
 *  name.
 *
 *  Sizes stay in theme spacing units and typography variants rather than raw
 *  pixels, so a compact tier still tracks the user's fontScale — it packs
 *  more in, it does not opt out of the accessibility scaling. The only raw-px
 *  values are the grid column bounds, which have to be pixels to feed
 *  `minmax()`.
 */

import { densityForCount } from '../ui/density';
import type { Density, DensityThresholds } from '../ui/density';

export interface RosterDensitySpec {
  /** Grid column bounds, px — feed `minmax()` in the roster grid. */
  minColumnPx: number;
  maxColumnPx: number;
  /** Typography variant for the neighbor's name. */
  nameVariant: 'subtitle1' | 'subtitle2' | 'body2';
  /** Typography variant for the callsign, location and status lines. */
  detailVariant: 'body2' | 'caption';
  /** Card padding and internal gap, in theme spacing units. */
  padding: number;
  gap: number;
}

const THRESHOLDS: DensityThresholds = { roomyMax: 6, mediumMax: 14 };

const SPECS: Record<Density, RosterDensitySpec> = {
  roomy: {
    minColumnPx: 280, maxColumnPx: 420,
    nameVariant: 'subtitle1', detailVariant: 'body2',
    padding: 1.5, gap: 0.5,
  },
  medium: {
    minColumnPx: 230, maxColumnPx: 320,
    nameVariant: 'subtitle2', detailVariant: 'body2',
    padding: 1.25, gap: 0.5,
  },
  compact: {
    minColumnPx: 190, maxColumnPx: 260,
    nameVariant: 'body2', detailVariant: 'caption',
    padding: 1, gap: 0.25,
  },
};

export function rosterDensityFor(rosterSize: number): Density {
  return densityForCount(rosterSize, THRESHOLDS);
}

export function rosterDensitySpec(rosterSize: number): RosterDensitySpec {
  return SPECS[rosterDensityFor(rosterSize)];
}

export interface IncidentDensitySpec {
  /** Grid column bounds, px — feed `minmax()` in the incident grid. */
  minColumnPx: number;
  maxColumnPx: number;
  /** Typography variant for the incident description — the thing you read. */
  bodyVariant: 'body1' | 'body2';
  /** Typography variant for the timestamp and the location/reporter line. */
  detailVariant: 'body2' | 'caption';
  /** Card padding and internal gap, in theme spacing units. */
  padding: number;
  gap: number;
}

/** Incidents tier earlier than roster rows: a card holds a free-text
 *  description, so eight of them already run past a screen where eight roster
 *  rows do not. */
const INCIDENT_THRESHOLDS: DensityThresholds = { roomyMax: 4, mediumMax: 10 };

const INCIDENT_SPECS: Record<Density, IncidentDensitySpec> = {
  roomy: {
    minColumnPx: 320, maxColumnPx: 480,
    bodyVariant: 'body1', detailVariant: 'body2',
    padding: 1.5, gap: 0.5,
  },
  medium: {
    minColumnPx: 260, maxColumnPx: 360,
    bodyVariant: 'body2', detailVariant: 'body2',
    padding: 1.25, gap: 0.5,
  },
  compact: {
    minColumnPx: 220, maxColumnPx: 300,
    bodyVariant: 'body2', detailVariant: 'caption',
    padding: 1, gap: 0.25,
  },
};

export function incidentDensityFor(incidentCount: number): Density {
  return densityForCount(incidentCount, INCIDENT_THRESHOLDS);
}

export function incidentDensitySpec(incidentCount: number): IncidentDensitySpec {
  return INCIDENT_SPECS[incidentDensityFor(incidentCount)];
}
