import './StatusRow.css';
import type { StatusMsg } from '../../types/ws';

interface Props {
  status: StatusMsg | null;
}

interface Tile {
  icon: string;
  label: string;
  ok: boolean | null;
  ariaLabel: string;
}

export function StatusRow({ status }: Props) {
  const tiles: Tile[] = [
    {
      icon: status === null ? '❓' : status.radio_connected ? '✅' : '❌',
      label: status === null
        ? 'Radio Cable: Checking...'
        : status.radio_connected
          ? 'Radio Cable Connected'
          : 'Radio Cable Disconnected',
      ok: status === null ? null : status.radio_connected,
      ariaLabel: status === null
        ? 'Radio cable status: checking'
        : status.radio_connected
          ? 'Radio cable: connected'
          : 'Radio cable: disconnected',
    },
    {
      icon: status === null ? '❓' : status.volume_ok ? '🔊' : '🔇',
      label: status === null
        ? 'Radio Volume: Checking...'
        : status.volume_ok
          ? 'Radio Volume is Perfect'
          : 'Radio Volume Needs Adjustment',
      ok: status === null ? null : status.volume_ok,
      ariaLabel: status === null
        ? 'Radio volume status: checking'
        : status.volume_ok
          ? 'Radio volume: perfect'
          : 'Radio volume: needs adjustment',
    },
    {
      icon: status === null ? '❓' : status.channel_clear ? '📡' : '⚠️',
      label: status === null
        ? 'Channel: Checking...'
        : status.channel_clear
          ? 'Channel: Clear'
          : 'Channel: Busy',
      ok: status === null ? null : status.channel_clear,
      ariaLabel: status === null
        ? 'Channel status: checking'
        : status.channel_clear
          ? 'Channel: clear'
          : 'Channel: busy',
    },
  ];

  return (
    <div className="status-row" role="status" aria-label="Radio hardware status">
      {tiles.map((tile) => (
        <div
          key={tile.ariaLabel}
          className={`status-tile ${tile.ok === true ? 'status-tile--ok' : tile.ok === false ? 'status-tile--error' : 'status-tile--unknown'}`}
          aria-label={tile.ariaLabel}
        >
          <span className="status-tile-icon" aria-hidden="true">{tile.icon}</span>
          <span className="status-tile-label">{tile.label}</span>
        </div>
      ))}
    </div>
  );
}
