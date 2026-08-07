import { useState } from 'react';
import { Box, Paper, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import type { StationPosition } from '../../types/ws';
import { visuallyHidden } from '../../ui/a11y';
import { PanelHeader } from '../PanelHeader/PanelHeader';
import { PositionList } from '../PositionList/PositionList';
import { MapPanel } from '../MapPanel/MapPanel';

interface Props {
  stations: StationPosition[];
  stationLat?: number | null;
  stationLon?: number | null;
  tilesLocal?: boolean;
  tilesUrl?: string;
  units?: 'mi' | 'km';
}

/**
 * Operator-side positions panel: the map, plus a list view that carries the
 * same information for anyone who can't use a map.
 *
 * The list is a first-class view rather than a fallback — it is the faster way
 * to read "who is nearest" during a net, and it is the only view an e-ink
 * kiosk or a screen reader can use at all.
 */
export function PositionsPanel({
  stations,
  stationLat,
  stationLon,
  tilesLocal,
  tilesUrl,
  units = 'mi',
}: Props) {
  const [view, setView] = useState<'map' | 'list'>('map');
  const hasOrigin = typeof stationLat === 'number' && typeof stationLon === 'number';

  return (
    <Paper square elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <PanelHeader
        title="Station positions"
        gradient="linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)"
      />

      <Box sx={{ px: 2, pt: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={view}
          onChange={(_e, next) => next && setView(next)}
          aria-label="Position view"
        >
          <ToggleButton value="map" aria-label="Map view">Map</ToggleButton>
          <ToggleButton value="list" aria-label="List view">List</ToggleButton>
        </ToggleButtonGroup>
        {/* Announced on change so the count is available without the map. */}
        <Typography variant="body2" role="status" sx={{ color: 'text.secondary' }}>
          {stations.length === 1 ? '1 station heard' : `${stations.length} stations heard`}
        </Typography>
      </Box>

      {!hasOrigin && (
        <Typography variant="body2" sx={{ px: 2, pt: 1, color: 'text.secondary' }}>
          Set this station's latitude and longitude in Settings → Station to get distance
          and bearing.
        </Typography>
      )}

      <Box sx={{ py: 1 }}>
        {view === 'map' ? (
          <>
            {/* The map itself is hidden from assistive tech, so this view
                would otherwise read as an empty region. Say where the data is
                instead of leaving someone to guess the toggle does anything. */}
            <Box component="p" sx={visuallyHidden}>
              The map is visual only. Choose List view for the same stations as text,
              nearest first.
            </Box>
            <MapPanel
              stations={stations}
              stationLat={stationLat}
              stationLon={stationLon}
              tilesLocal={tilesLocal}
              tilesUrl={tilesUrl}
              units={units}
            />
          </>
        ) : (
          <PositionList stations={stations} units={units} />
        )}
      </Box>
    </Paper>
  );
}
