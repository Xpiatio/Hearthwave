import { render, screen, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { axe } from 'jest-axe';
import { PositionList } from './PositionList';
import type { StationPosition } from '../../types/ws';

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

describe('PositionList', () => {
  it('renders one row per station in the order given', () => {
    render(
      <PositionList
        stations={[
          station({ node_id: 'a', label: 'Near', distance_km: 1 }),
          station({ node_id: 'b', label: 'Far', distance_km: 50 }),
        ]}
      />,
    );
    const rows = screen.getAllByRole('row').slice(1); // drop the header row
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText('Near')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Far')).toBeInTheDocument();
  });

  it('makes the station name the row header, so a row reads as one station', () => {
    render(<PositionList stations={[station({ label: 'Near' })]} />);
    expect(screen.getByRole('rowheader', { name: 'Near' })).toBeInTheDocument();
  });

  it('falls back to the node id when a station advertises no name', () => {
    render(<PositionList stations={[station({ label: '', node_id: 'W8ABC-9' })]} />);
    expect(screen.getByText('W8ABC-9')).toBeInTheDocument();
  });

  it('spells the compass point out for screen readers', () => {
    render(<PositionList stations={[station({ compass: 'WSW' })]} />);
    expect(screen.getByText('WSW')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByText('west-southwest')).toBeInTheDocument();
  });

  it('shows a dash for bearing when there is no own position', () => {
    render(<PositionList stations={[station({ compass: null, distance_km: null })]} />);
    expect(screen.getAllByText('—')).toHaveLength(2);
  });

  it('explains itself rather than showing an empty table', () => {
    render(<PositionList stations={[]} />);
    expect(screen.getByText(/no station positions received yet/i)).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('takes a caller-supplied empty caption', () => {
    render(<PositionList stations={[]} emptyText="Nothing heard on the mesh." />);
    expect(screen.getByText('Nothing heard on the mesh.')).toBeInTheDocument();
  });

  it('passes axe', async () => {
    const { container } = render(
      <PositionList stations={[station(), station({ node_id: 'b', source: 'aprs_rf' })]} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('passes axe on an e-ink panel', async () => {
    const { container } = render(<PositionList stations={[station()]} eink />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
