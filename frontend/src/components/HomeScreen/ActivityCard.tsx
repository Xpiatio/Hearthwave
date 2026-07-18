import { ButtonBase, Paper, Typography, Box } from '@mui/material';

interface Props {
  emoji: string;
  title: string;
  subtitle?: string;
  /** Unread count for this activity (e.g. unseen chat messages). When
   *  nonzero it's folded into the accessible name — aria-label overrides
   *  the button's text content for the accessible name, so without this
   *  the "N new" subtitle text is invisible to screen readers. */
  unreadCount?: number;
  /** Free-form alert phrase (e.g. "2 missed check-ins") folded into the
   *  accessible name the same way unreadCount is — for statuses that
   *  aren't a plain count of "new" items. Ignored when unreadCount is set.
   *  Callers should only pass this for states that need surfacing (an
   *  all-clear subtitle like "Everyone OK" need not be in the name). */
  alertText?: string;
  onClick: () => void;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  onFocus?: () => void;
  buttonRef?: (el: HTMLButtonElement | null) => void;
}

/** Large tap-target card for the home activity grid (AAC-style sizing). */
export function ActivityCard({
  emoji, title, subtitle, unreadCount, alertText, onClick, tabIndex, onKeyDown, onFocus, buttonRef,
}: Props) {
  const accessibleName = unreadCount
    ? `${title}, ${unreadCount} new`
    : alertText
      ? `${title}, ${alertText}`
      : title;
  return (
    <ButtonBase
      onClick={onClick}
      aria-label={accessibleName}
      tabIndex={tabIndex}
      onKeyDown={onKeyDown}
      onFocus={onFocus}
      ref={buttonRef}
      sx={{ borderRadius: 2, width: '100%', height: '100%', textAlign: 'left' }}
    >
      <Paper
        sx={{
          p: 3, width: '100%', height: '100%', minHeight: 140, display: 'flex',
          flexDirection: 'column', gap: 1, justifyContent: 'center',
        }}
      >
        <Box component="span" aria-hidden sx={{ fontSize: '2.5rem', lineHeight: 1 }}>
          {emoji}
        </Box>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">{subtitle}</Typography>
        )}
      </Paper>
    </ButtonBase>
  );
}
