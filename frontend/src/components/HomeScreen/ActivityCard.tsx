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
  onClick: () => void;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  onFocus?: () => void;
  buttonRef?: (el: HTMLButtonElement | null) => void;
}

/** Large tap-target card for the home activity grid (AAC-style sizing). */
export function ActivityCard({
  emoji, title, subtitle, unreadCount, onClick, tabIndex, onKeyDown, onFocus, buttonRef,
}: Props) {
  const accessibleName = unreadCount ? `${title}, ${unreadCount} new` : title;
  return (
    <ButtonBase
      onClick={onClick}
      aria-label={accessibleName}
      tabIndex={tabIndex}
      onKeyDown={onKeyDown}
      onFocus={onFocus}
      ref={buttonRef}
      sx={{ borderRadius: 2, width: '100%', textAlign: 'left' }}
    >
      <Paper
        sx={{
          p: 3, width: '100%', minHeight: 140, display: 'flex',
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
