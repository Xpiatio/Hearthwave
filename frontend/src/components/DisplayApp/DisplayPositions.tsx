import { Box, Typography } from '@mui/material';
import type { StationPosition } from '../../types/ws';
import { PositionList } from '../PositionList/PositionList';
import { MapPanel } from '../MapPanel/MapPanel';

/** Nearest few only — a wall panel is read from across the room, not scrolled. */
export const KIOSK_ROWS = 6;

interface Props {
  stations: StationPosition[];
  stationLat?: number | null;
  stationLon?: number | null;
  tilesLocal?: boolean;
  tilesUrl?: string;
  /** E-ink panels get the list; a map on e-ink is unreadable and smears. */
  eink: boolean;
}

/**
 * Positions block for the kiosk.
 *
 * E-ink shows a distance-sorted list: no tiles to render, nothing that moves,
 * nothing that needs a partial refresh. Every other panel shows the map.
 * Renders nothing at all when no position has been heard, so an install with
 * no position sources sees no empty furniture on the wall.
 */
export function DisplayPositions({
  stations,
  stationLat,
  stationLon,
  tilesLocal,
  tilesUrl,
  eink,
}: Props) {
  if (stations.length === 0) return null;

  return (
    <Box component="section" aria-label="Station positions" sx={{ flexShrink: 0 }}>
      <Typography component="h2" sx={{ fontSize: '1.25rem', fontWeight: 700, mb: 0.5 }}>
        Stations heard
      </Typography>
      {eink ? (
        <PositionList stations={stations.slice(0, KIOSK_ROWS)} eink />
      ) : (
        <MapPanel
          stations={stations}
          stationLat={stationLat}
          stationLon={stationLon}
          tilesLocal={tilesLocal}
          tilesUrl={tilesUrl}
          height={260}
        />
      )}
    </Box>
  );
}
