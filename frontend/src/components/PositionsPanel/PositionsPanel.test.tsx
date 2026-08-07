import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { PositionsPanel } from './PositionsPanel';
import type { StationPosition } from '../../types/ws';

// jsdom has no layout and no canvas, so Leaflet cannot run here. These tests
// are about which view the panel shows; MapPanel.test.tsx covers the drawing.
vi.mock('leaflet', () => ({
  map: () => ({ setView: () => undefined, getZoom: () => 11, remove: () => undefined }),
  tileLayer: () => ({ addTo: () => undefined }),
  layerGroup: () => {
    const group = { clearLayers: () => undefined, addTo: () => group };
    return group;
  },
  circleMarker: () => {
    const marker = { bindPopup: () => marker, addTo: () => marker, setLatLng: () => marker };
    return marker;
  },
}));

function station(overrides: Partial<StationPosition> = {}): StationPosition {
  return {
    source: 'meshtastic',
    node_id: '!a1b2c3d4',
    label: 'Base',
    lat: 42.9,
    lon: -85.6,
    alt_m: null,
    age_s: 30,
    distance_km: 4.2,
    bearing_deg: 30,
    compass: 'NNE',
    extra: {},
    ...overrides,
  };
}

const ORIGIN = { stationLat: 42.9634, stationLon: -85.6681 };

describe('PositionsPanel', () => {
  it('opens on the map view', () => {
    render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('switches to the list view and back', () => {
    render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);

    fireEvent.click(screen.getByRole('button', { name: /list view/i }));
    expect(screen.getByRole('table', { name: /station positions/i })).toBeInTheDocument();
    expect(screen.queryByTestId('map-container')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /map view/i }));
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
  });

  it('points a screen reader at the list, since the map is hidden from it', () => {
    render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    expect(screen.getByText(/choose list view for the same stations as text/i))
      .toBeInTheDocument();
  });

  it('drops that pointer once the list is the view', () => {
    render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    fireEvent.click(screen.getByRole('button', { name: /list view/i }));
    expect(screen.queryByText(/choose list view/i)).not.toBeInTheDocument();
  });

  it('announces the station count without needing the map', () => {
    render(<PositionsPanel stations={[station(), station({ node_id: 'b' })]} {...ORIGIN} tilesLocal />);
    expect(screen.getByRole('status')).toHaveTextContent('2 stations heard');
  });

  it('says "1 station" rather than "1 stations"', () => {
    render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    expect(screen.getByRole('status')).toHaveTextContent('1 station heard');
  });

  it('tells the operator where to set the coordinates when there is no origin', () => {
    render(<PositionsPanel stations={[station({ distance_km: null, compass: null })]} tilesLocal />);
    expect(screen.getByText(/latitude and longitude in settings/i)).toBeInTheDocument();
  });

  it('drops that hint once an origin is configured', () => {
    render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    expect(screen.queryByText(/latitude and longitude in settings/i)).not.toBeInTheDocument();
  });

  it('passes axe in the map view', async () => {
    const { container } = render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('passes axe in the list view', async () => {
    const { container } = render(<PositionsPanel stations={[station()]} {...ORIGIN} tilesLocal />);
    fireEvent.click(screen.getByRole('button', { name: /list view/i }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
