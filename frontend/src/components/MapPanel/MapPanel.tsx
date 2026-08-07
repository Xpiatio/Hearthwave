import { useEffect, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import type * as Leaflet from 'leaflet';
import type { Map as LeafletMap, CircleMarker, LayerGroup } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { StationPosition } from '../../types/ws';
import { formatAge, formatDistance, sourceLabel } from '../PositionList/format';

/** Marker colour per source, so a station heard two ways is visibly two dots. */
const SOURCE_COLORS: Record<string, string> = {
  meshtastic: '#22C55E',
  meshcore: '#38BDF8',
  aprs_rf: '#F59E0B',
};
const OTHER_COLOR = '#A78BFA';
const OWN_COLOR = '#EF4444';

/** Tiles the backend serves from the offline pack in /data/tiles. */
export const LOCAL_TILES_URL = '/tiles/{z}/{x}/{y}.png';

const DEFAULT_ZOOM = 11;
/** Centre of the contiguous US — only used when no own position is set. */
const FALLBACK_CENTER: [number, number] = [39.5, -98.35];

interface Props {
  stations: StationPosition[];
  /** Own station; the map centres here when both are set. */
  stationLat?: number | null;
  stationLon?: number | null;
  /** True when the server is serving an offline tile pack at /tiles. */
  tilesLocal?: boolean;
  /** Remote XYZ template, used only when there is no local pack. */
  tilesUrl?: string;
  units?: 'mi' | 'km';
  height?: number | string;
}

/**
 * Leaflet map of every heard station.
 *
 * Leaflet is driven imperatively from an effect rather than through
 * react-leaflet: one less version-coupled dependency, and the only React state
 * involved is "which stations exist", which a diff-free redraw of a single
 * layer group handles fine.
 *
 * Markers are circles, not pins, deliberately — Leaflet's default pin is a
 * bundled PNG whose URL breaks under Vite, and a circle needs no asset at all.
 *
 * A map is not usable without sight. This component is therefore never the
 * only way to read positions: PositionsPanel pairs it with the list view, and
 * the map is hidden from assistive technology *and* taken out of the tab order
 * (see the container below), so nobody navigating by keyboard or screen reader
 * has to walk through a pan-and-zoom canvas to reach the data.
 */
export function MapPanel({
  stations,
  stationLat,
  stationLon,
  tilesLocal = false,
  tilesUrl = '',
  units = 'mi',
  height = 360,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const ownRef = useRef<CircleMarker | null>(null);
  // Held so the draw effects below stay synchronous; the dynamic import is
  // resolved exactly once, in the create effect.
  const leafletRef = useRef<typeof Leaflet | null>(null);
  // Map creation is async (dynamic import), so the draw effects below would
  // otherwise race it and silently skip the first batch of stations.
  const [mapReady, setMapReady] = useState(false);

  const tileTemplate = tilesLocal ? LOCAL_TILES_URL : tilesUrl;
  const hasOrigin = typeof stationLat === 'number' && typeof stationLon === 'number';

  // Create the map once. Leaflet owns the DOM inside the container, so this
  // must not re-run on every render or it would stack maps on one element.
  useEffect(() => {
    let cancelled = false;
    // Dynamic import keeps Leaflet out of the initial bundle for the kiosks
    // and mobile views that never open a map.
    import('leaflet').then((L) => {
      if (cancelled || !containerRef.current || mapRef.current) return;
      const map = L.map(containerRef.current, {
        center: FALLBACK_CENTER,
        zoom: DEFAULT_ZOOM,
        attributionControl: true,
        // No keyboard handler: it would put tabindex="0" on a container that
        // is aria-hidden, which is both an axe violation and a dead stop for
        // anyone tabbing through. The list view is the keyboard path.
        keyboard: false,
      });
      if (tileTemplate) {
        L.tileLayer(tileTemplate, { maxZoom: 19 }).addTo(map);
      }
      layerRef.current = L.layerGroup().addTo(map);
      leafletRef.current = L;
      mapRef.current = map;
      setMapReady(true);
    });
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
      ownRef.current = null;
      leafletRef.current = null;
    };
    // The tile template is read at creation; changing it needs a page reload,
    // which is what a settings save already causes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recentre on the own-station marker whenever it moves.
  useEffect(() => {
    const L = leafletRef.current;
    const map = mapRef.current;
    if (!mapReady || !hasOrigin || !L || !map) return;
    const center: [number, number] = [stationLat as number, stationLon as number];
    map.setView(center, map.getZoom());
    if (ownRef.current) {
      ownRef.current.setLatLng(center);
    } else {
      ownRef.current = L.circleMarker(center, {
        radius: 8,
        color: OWN_COLOR,
        fillColor: OWN_COLOR,
        fillOpacity: 0.9,
        weight: 2,
      })
        .bindPopup('This station')
        .addTo(map);
    }
  }, [mapReady, hasOrigin, stationLat, stationLon]);

  // Redraw the station markers. Clearing the layer group and re-adding is
  // cheaper than diffing at the sizes involved (the store caps at 500) and
  // avoids holding a second index of markers alive.
  useEffect(() => {
    const L = leafletRef.current;
    const layer = layerRef.current;
    if (!mapReady || !L || !layer) return;
    layer.clearLayers();
    for (const s of stations) {
      const color = SOURCE_COLORS[s.source] ?? OTHER_COLOR;
      L.circleMarker([s.lat, s.lon], {
        radius: 6,
        color,
        fillColor: color,
        fillOpacity: 0.8,
        weight: 2,
      })
        .bindPopup(popupHtml(s, units))
        .addTo(layer);
    }
  }, [mapReady, stations, units]);

  return (
    <Box>
      {!tileTemplate && (
        <Typography variant="body2" sx={{ px: 2, py: 1, color: 'text.secondary' }}>
          No map tiles configured. Install an offline tile pack in /data/tiles, or set a
          tile URL in Settings → Station.
        </Typography>
      )}
      {/* Hidden from assistive tech on purpose: a pan-and-zoom canvas conveys
          nothing to a screen reader, and the list view carries the same data.
          `inert` goes with it — Leaflet adds zoom buttons and an attribution
          link inside, and focusable controls inside an aria-hidden subtree are
          exactly the trap the attribute is meant to prevent. */}
      <Box
        ref={containerRef}
        aria-hidden="true"
        inert
        data-testid="map-container"
        sx={{ height, width: '100%', bgcolor: 'action.hover' }}
      />
    </Box>
  );
}

/** Popup body. Escaped, because labels and APRS comments are remote input. */
export function popupHtml(s: StationPosition, units: 'mi' | 'km'): string {
  const rows = [
    `<strong>${escapeHtml(s.label || s.node_id)}</strong>`,
    escapeHtml(sourceLabel(s.source)),
  ];
  if (s.distance_km !== null) {
    rows.push(
      escapeHtml(`${formatDistance(s.distance_km, units)} ${s.compass ?? ''}`.trim()),
    );
  }
  rows.push(escapeHtml(`Heard ${formatAge(s.age_s)}`));
  for (const [key, value] of Object.entries(s.extra ?? {})) {
    rows.push(escapeHtml(`${key}: ${value}`));
  }
  return rows.join('<br>');
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
