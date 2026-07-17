import { useRef, useState } from 'react';
import { Box, Typography, IconButton, Tooltip, Chip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import { Logo } from '../Logo/Logo';
import { ActivityCard } from './ActivityCard';
import type { UserProfile } from '../../types/ws';

interface Props {
  profile: UserProfile;
  connected: boolean;
  uiLevel: 'simple' | 'operator';
  ncsEnabled: boolean;
  unreadCount: number;
  onOpenActivity: (a: 'station' | 'ncs') => void;
  onOpenSettings: () => void;
  onLogout: () => void;
}

interface CardDef {
  key: string;
  emoji: string;
  title: string;
  subtitle?: string;
  onClick: () => void;
}

/** Home shell: glance header + activity card grid. Default landing screen. */
export function HomeScreen(props: Props) {
  const cards: CardDef[] = [
    {
      key: 'chat', emoji: '💬', title: 'Chat',
      subtitle: props.unreadCount > 0 ? `${props.unreadCount} new` : 'Talk on the radio',
      onClick: () => props.onOpenActivity('station'),
    },
  ];
  if (props.uiLevel === 'operator' && props.ncsEnabled) {
    cards.push({
      key: 'ncs', emoji: '🎙', title: 'Net Control',
      subtitle: 'Run a net', onClick: () => props.onOpenActivity('ncs'),
    });
  }

  // Roving tabindex: one card is tabbable; arrows move focus.
  const [focusIdx, setFocusIdx] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  // Clamp so a stale focusIdx (e.g. cards shrank because uiLevel/ncsEnabled
  // changed) never points past the end — otherwise every card would land at
  // tabIndex -1 and the grid would become unreachable by keyboard.
  const effectiveFocusIdx = Math.min(focusIdx, cards.length - 1);
  function handleKeyDown(e: React.KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % cards.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + cards.length) % cards.length;
    else return;
    e.preventDefault();
    setFocusIdx(next);
    refs.current[next]?.focus();
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', p: { xs: 2, md: 4 }, gap: 3 }}>
      <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Logo />
        <Typography variant="h5" sx={{ fontWeight: 700, flexGrow: 1 }}>
          Hearthwave
        </Typography>
        <Chip
          size="small"
          color={props.connected ? 'success' : 'error'}
          label={props.connected ? 'Connected' : 'Disconnected'}
        />
        <Tooltip title="Settings">
          <IconButton aria-label="Settings" onClick={props.onOpenSettings}><SettingsIcon /></IconButton>
        </Tooltip>
        <Tooltip title="Log out">
          <IconButton aria-label="Log out" onClick={props.onLogout}><LogoutIcon /></IconButton>
        </Tooltip>
      </Box>

      <Typography variant="h6">
        Welcome, {props.profile.display_name} {props.profile.avatar_emoji}
      </Typography>

      <Box
        role="list"
        aria-label="Activities"
        sx={{
          display: 'grid', gap: 2,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
          alignContent: 'start', flexGrow: 1,
        }}
      >
        {cards.map((c, i) => (
          <Box role="listitem" key={c.key}>
            <ActivityCard
              emoji={c.emoji}
              title={c.title}
              subtitle={c.subtitle}
              onClick={c.onClick}
              buttonRef={(el) => { refs.current[i] = el; }}
              tabIndex={i === effectiveFocusIdx ? 0 : -1}
              onKeyDown={(e) => handleKeyDown(e, i)}
              onFocus={() => setFocusIdx(i)}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
}
