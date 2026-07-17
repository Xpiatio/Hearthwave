import { ButtonBase, Paper, Typography, Box } from '@mui/material';

interface Props {
  emoji: string;
  title: string;
  subtitle?: string;
  onClick: () => void;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  onFocus?: () => void;
  buttonRef?: (el: HTMLButtonElement | null) => void;
}

/** Large tap-target card for the home activity grid (AAC-style sizing). */
export function ActivityCard({
  emoji, title, subtitle, onClick, tabIndex, onKeyDown, onFocus, buttonRef,
}: Props) {
  return (
    <ButtonBase
      onClick={onClick}
      aria-label={title}
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
