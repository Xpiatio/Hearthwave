import { Box, Button, ButtonBase, IconButton, Tooltip, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import type { FamilyPresenceEntry, UserProfile } from '../../types/ws';
import { MemberCard } from './MemberCard';
import { ReminderEditor } from './ReminderEditor';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';

export interface FamilyPanelProps {
  profile: UserProfile;
  entries: FamilyPresenceEntry[];
  reminders: Record<string, { time: string; enabled: boolean }>;
  isKid: boolean;
  isAdmin: boolean;
  quickMessages: string[];
  onImOk: () => void;
  onQuickMessage: (text: string) => void;
  onSetReminder: (userId: string, time: string | null, enabled: boolean) => void;
  onGoHome: () => void;
}

/** Full-screen family activity: presence board, giant "I'm OK" check-in
 *  button, quick messages, and (admin-only, not for kid accounts)
 *  per-member check-in reminder editors.
 *
 *  Rendered as a sibling of DesktopApp in App.tsx's shell ladder (mirroring
 *  HomeScreen), so it owns its own Escape-to-home binding rather than
 *  relying on DesktopApp's — the two are never mounted at once. */
export function FamilyPanel(props: FamilyPanelProps) {
  useEscapeToHome(props.onGoHome);
  const now = new Date();
  const showReminders = props.isAdmin && !props.isKid;

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', p: { xs: 2, md: 4 }, gap: 3 }}>
      <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Tooltip title="Back to home">
          <IconButton aria-label="Back to home" onClick={props.onGoHome}>
            <ArrowBackIcon />
          </IconButton>
        </Tooltip>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Family
        </Typography>
      </Box>

      <Box
        role="list"
        aria-label="Family members"
        sx={{
          display: 'grid', gap: 2,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
        }}
      >
        {props.entries.map((entry) => (
          <Box role="listitem" key={entry.user_id}>
            <MemberCard entry={entry} now={now} />
          </Box>
        ))}
      </Box>

      <ButtonBase
        onClick={props.onImOk}
        aria-label="I'm OK"
        sx={{
          minHeight: 96,
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 2,
          fontSize: '1.4rem',
          fontWeight: 700,
          gap: 1.5,
          bgcolor: 'success.main',
          color: 'success.contrastText',
        }}
      >
        <Box component="span" aria-hidden>✅</Box>
        I&apos;m OK
      </ButtonBase>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
        {props.quickMessages.map((text) => (
          <Button
            key={text}
            variant="outlined"
            onClick={() => props.onQuickMessage(text)}
            sx={{ minHeight: 56, textTransform: 'none' }}
          >
            {text}
          </Button>
        ))}
      </Box>

      {showReminders && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Check-in reminders
          </Typography>
          {props.entries.map((entry) => {
            const reminder = props.reminders[entry.user_id] ?? { time: '', enabled: false };
            return (
              <ReminderEditor
                key={entry.user_id}
                userId={entry.user_id}
                name={entry.display_name}
                time={reminder.time}
                enabled={reminder.enabled}
                onSetReminder={props.onSetReminder}
              />
            );
          })}
        </Box>
      )}
    </Box>
  );
}
