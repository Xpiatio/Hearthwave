import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { axe } from 'jest-axe';
import { MapPanel, LOCAL_TILES_URL, popupHtml } from './MapPanel';
import type { StationPosition } from '../../types/ws';

// Leaflet needs real layout and a real canvas, neither of which jsdom has.
// The panel's own logic is "what did it ask Leaflet to draw", so record the
// calls instead: tile template, centre, and one marker per station.
const calls = {
  maps: [] as Array<{ options: unknown }>,
  tileLayers: [] as string[],
  circleMarkers: [] as Array<{ latlng: [number, number]; options: Record<string, unknown> }>,
  popups: [] as string[],
  setViews: [] as Array<[number, number]>,
  clears: 0,
  removes: 0,
};

vi.mock('leaflet', () => {
  function marker(latlng: [number, number], options: Record<string, unknown>) {
    calls.circleMarkers.push({ latlng, options });
    const self = {
      bindPopup(html: string) {
        calls.popups.push(html);
        return self;
      },
      addTo() {
        return self;
      },
      setLatLng(next: [number, number]) {
        calls.setViews.push(next);
        return self;
      },
    };
    return self;
  }
  return {
    map: (_el: HTMLElement, options: unknown) => {
      calls.maps.push({ options });
      return {
        setView: (center: [number, number]) => calls.setViews.push(center),
        getZoom: () => 11,
        remove: () => {
          calls.removes += 1;
        },
      };
    },
    tileLayer: (template: string) => {
      calls.tileLayers.push(template);
      return { addTo: () => undefined };
    },
    layerGroup: () => {
      const group = {
        clearLayers: () => {
          calls.clears += 1;
        },
        addTo: () => group,
      };
      return group;
    },
    circleMarker: marker,
  };
});

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

beforeEach(() => {
  calls.maps = [];
  calls.tileLayers = [];
  calls.circleMarkers = [];
  calls.popups = [];
  calls.setViews = [];
  calls.clears = 0;
  calls.removes = 0;
});

describe('MapPanel', () => {
  it('serves tiles from the offline pack when the server has one', async () => {
    render(<MapPanel stations={[]} tilesLocal />);
    await waitFor(() => expect(calls.tileLayers).toEqual([LOCAL_TILES_URL]));
  });

  it('falls back to the configured remote template when there is no pack', async () => {
    render(<MapPanel stations={[]} tilesUrl="https://tiles.example/{z}/{x}/{y}.png" />);
    await waitFor(() =>
      expect(calls.tileLayers).toEqual(['https://tiles.example/{z}/{x}/{y}.png']),
    );
  });

  it('prefers the local pack over a remote URL — offline is the point', async () => {
    render(<MapPanel stations={[]} tilesLocal tilesUrl="https://tiles.example/{z}/{x}/{y}.png" />);
    await waitFor(() => expect(calls.tileLayers).toEqual([LOCAL_TILES_URL]));
  });

  it('says so, and adds no tile layer, when no tiles are configured', async () => {
    render(<MapPanel stations={[]} />);
    expect(screen.getByText(/no map tiles configured/i)).toBeInTheDocument();
    await waitFor(() => expect(calls.maps).toHaveLength(1));
    expect(calls.tileLayers).toEqual([]);
  });

  it('centres on the own station once coordinates are set', async () => {
    render(<MapPanel stations={[]} stationLat={42.9} stationLon={-85.6} tilesLocal />);
    await waitFor(() => expect(calls.setViews).toContainEqual([42.9, -85.6]));
  });

  it('leaves the map at its fallback centre when no own position is configured', async () => {
    render(<MapPanel stations={[]} tilesLocal />);
    await waitFor(() => expect(calls.maps).toHaveLength(1));
    expect(calls.setViews).toEqual([]);
  });

  it('draws one marker per station', async () => {
    render(<MapPanel stations={[station({ node_id: 'a' }), station({ node_id: 'b' })]} tilesLocal />);
    await waitFor(() => expect(calls.circleMarkers).toHaveLength(2));
  });

  it('colours markers by source so one station heard twice reads as two dots', async () => {
    render(
      <MapPanel
        stations={[station({ source: 'meshtastic' }), station({ node_id: 'b', source: 'aprs_rf' })]}
        tilesLocal
      />,
    );
    await waitFor(() => expect(calls.circleMarkers).toHaveLength(2));
    const colors = calls.circleMarkers.map((m) => m.options.color);
    expect(new Set(colors).size).toBe(2);
  });

  it('tears the map down on unmount rather than leaking it', async () => {
    const { unmount } = render(<MapPanel stations={[]} tilesLocal />);
    await waitFor(() => expect(calls.maps).toHaveLength(1));
    unmount();
    expect(calls.removes).toBe(1);
  });

  it('hides the canvas from assistive tech — the list view carries the data', () => {
    render(<MapPanel stations={[station()]} tilesLocal />);
    const container = screen.getByTestId('map-container');
    expect(container).toHaveAttribute('aria-hidden', 'true');
    // Leaflet's zoom buttons and attribution link live in here; focusable
    // controls inside an aria-hidden subtree are a keyboard trap.
    expect(container).toHaveAttribute('inert');
  });

  it('turns off Leaflet keyboard handling — it would tabindex the hidden container', async () => {
    render(<MapPanel stations={[]} tilesLocal />);
    await waitFor(() => expect(calls.maps).toHaveLength(1));
    expect(calls.maps[0].options).toMatchObject({ keyboard: false });
  });

  it('passes axe', async () => {
    const { container } = render(<MapPanel stations={[station()]} tilesLocal />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('popupHtml', () => {
  it('leads with the station name and its source', () => {
    const html = popupHtml(station(), 'mi');
    expect(html).toContain('<strong>Base</strong>');
    expect(html).toContain('Meshtastic');
  });

  it('includes distance with the bearing, and the age', () => {
    const html = popupHtml(station(), 'mi');
    expect(html).toContain('2.6 mi NNE');
    expect(html).toContain('Heard now');
  });

  it('omits distance entirely when there is no own position', () => {
    const html = popupHtml(station({ distance_km: null, compass: null }), 'mi');
    expect(html).not.toContain('mi');
  });

  it('escapes remote text — labels and APRS comments are attacker-controlled', () => {
    const html = popupHtml(
      station({ label: '<img src=x onerror=alert(1)>', extra: { comment: '"&<b>' } }),
      'mi',
    );
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
    expect(html).toContain('&quot;&amp;&lt;b&gt;');
  });

  it("escapes the apostrophe too — it closes a single-quoted attribute", () => {
    const html = popupHtml(station({ label: "O'Brien' onmouseover='x" }), 'mi');
    expect(html).not.toContain("'");
    expect(html).toContain('&#39;');
  });

  it('appends whatever extras the source plugin attached', () => {
    const html = popupHtml(station({ extra: { alt_m: '218', snr: '6.2 dB' } }), 'mi');
    expect(html).toContain('alt_m: 218');
    expect(html).toContain('snr: 6.2 dB');
  });
});
