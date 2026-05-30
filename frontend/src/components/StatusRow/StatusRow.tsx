import { Box, Paper, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import HelpOutlinedIcon from '@mui/icons-material/HelpOutlined';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import VolumeOffIcon from '@mui/icons-material/VolumeOff';
import WifiIcon from '@mui/icons-material/Wifi';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import type { ElementType } from 'react';
import type { StatusMsg } from '../../types/ws';

interface Props {
  status: StatusMsg | null;
}

interface Tile {
  Icon: ElementType;
  label: string;
  state: 'ok' | 'error' | 'unknown';
  ariaLabel: string;
}

export function StatusRow({ status }: Props) {
  const tiles: Tile[] = [
    {
      Icon: status === null ? HelpOutlinedIcon : status.radio_connected ? CheckCircleIcon : CancelIcon,
      label: status === null
        ? 'Radio Cable: Checking...'
        : status.radio_connected
          ? 'Radio Cable Connected'
          : 'Radio Cable Disconnected',
      state: status === null ? 'unknown' : status.radio_connected ? 'ok' : 'error',
      ariaLabel: status === null
        ? 'Radio cable status: checking'
        : status.radio_connected
          ? 'Radio cable: connected'
          : 'Radio cable: disconnected',
    },
    {
      Icon: status === null ? HelpOutlinedIcon : status.volume_ok ? VolumeUpIcon : VolumeOffIcon,
      label: status === null
        ? 'Radio Volume: Checking...'
        : status.volume_ok
          ? 'Radio Volume is Perfect'
          : 'Radio Volume Needs Adjustment',
      state: status === null ? 'unknown' : status.volume_ok ? 'ok' : 'error',
      ariaLabel: status === null
        ? 'Radio volume status: checking'
        : status.volume_ok
          ? 'Radio volume: perfect'
          : 'Radio volume: needs adjustment',
    },
    {
      Icon: status === null ? HelpOutlinedIcon : status.channel_clear ? WifiIcon : WarningAmberIcon,
      label: status === null
        ? 'Channel: Checking...'
        : status.channel_clear
          ? 'Channel: Clear'
          : 'Channel: Busy',
      state: status === null ? 'unknown' : status.channel_clear ? 'ok' : 'error',
      ariaLabel: status === null
        ? 'Channel status: checking'
        : status.channel_clear
          ? 'Channel: clear'
          : 'Channel: busy',
    },
  ];

  const borderColor: Record<Tile['state'], string> = {
    ok: 'success.main',
    error: 'error.main',
    unknown: 'text.disabled',
  };

  const iconColor: Record<Tile['state'], 'success' | 'error' | 'disabled'> = {
    ok: 'success',
    error: 'error',
    unknown: 'disabled',
  };

  return (
    <Box
      sx={{ display: 'flex', gap: 1, px: 1, py: 0.75, bgcolor: 'background.paper' }}
      role="status"
      aria-label="Radio hardware status"
    >
      {tiles.map((tile) => (
        <Paper
          key={tile.ariaLabel}
          elevation={0}
          variant="outlined"
          aria-label={tile.ariaLabel}
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.5,
            py: 1,
            borderLeftWidth: 3,
            borderLeftColor: borderColor[tile.state],
            borderRadius: 1,
          }}
        >
          <tile.Icon fontSize="small" color={iconColor[tile.state]} aria-hidden="true" />
          <Typography
            variant="body2"
            sx={{ fontWeight: 600, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}
          >
            {tile.label}
          </Typography>
        </Paper>
      ))}
    </Box>
  );
}
