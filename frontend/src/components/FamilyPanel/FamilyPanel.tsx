import { Box, Button, ButtonBase, IconButton, Tooltip, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import type { FamilyPresenceEntry } from '../../types/ws';
import { MemberCard } from './MemberCard';
import { ReminderEditor } from './ReminderEditor';
import { densitySpec } from '../../family/density';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';
import { useDayKey } from '../../hooks/useDayKey';

export interface FamilyPanelProps {
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
  // "OK ✓ 9:15" hides the date only while it means today — the midnight
  // re-render is what keeps that true on a board left up overnight.
  useDayKey();
  const now = new Date();
  const showReminders = props.isAdmin && !props.isKid;
  // Cards get roomier for a small household and tighter for a big one, so a
  // large family still fits on screen. See family/density.ts.
  const density = densitySpec(props.entries.length);

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
        sx={{
          display: 'grid', gap: 2, justifyContent: 'start',
          // auto-fit packs as many columns as the viewport allows; the tier's
          // max keeps a two-person household from becoming two billboards, and
          // min(…, 100%) stops a card overflowing a phone-width screen.
          gridTemplateColumns:
            `repeat(auto-fit, minmax(min(${density.minColumnPx}px, 100%), ${density.maxColumnPx}px))`,
        }}
      >
        {/* "I'm OK" leads the board as a tile the same size as a member card,
            so the thing you came here to press sits where your eye lands
            first. It is deliberately outside the member list — it is an
            action, not a person. */}
        <ButtonBase
          onClick={props.onImOk}
          aria-label="I'm OK"
          sx={{
            height: '100%',
            minHeight: 96,
            p: density.padding,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: density.gap,
            borderRadius: 2,
            fontWeight: 700,
            bgcolor: 'success.main',
            color: 'success.contrastText',
          }}
        >
          <Box component="span" aria-hidden sx={{ fontSize: density.emojiFontSize, lineHeight: 1 }}>
            ✅
          </Box>
          <Typography variant={density.nameVariant} sx={{ fontWeight: 700 }}>
            I&apos;m OK
          </Typography>
        </ButtonBase>

        {/* display: contents lets the member cards be grid items of the board
            above while still sitting inside their own list, so the button
            isn't announced as a family member. */}
        <Box role="list" aria-label="Family members" sx={{ display: 'contents' }}>
          {props.entries.map((entry) => (
            <Box role="listitem" key={entry.user_id}>
              <MemberCard entry={entry} now={now} density={density} />
            </Box>
          ))}
        </Box>
      </Box>

      {props.isKid && props.quickMessages.length === 0 ? (
        <Box sx={{ p: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Ask an adult to set up your messages.
          </Typography>
        </Box>
      ) : (
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
      )}

      {showReminders && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Check-in reminders
          </Typography>
          {/* mt: -1 pulls the blurb up against its header, past the stack's gap: 2. */}
          <Typography variant="caption" sx={{ mt: -1, color: 'text.secondary' }}>
            Set a daily time for each person. If they haven&apos;t tapped &quot;I&apos;m OK&quot; by
            then, their card here shows &quot;Missed check-in&quot;, the Family card on Home raises
            an alert, and (if notifications are on) this device gets a notification. Use the
            switch to pause a reminder without clearing its time.
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
