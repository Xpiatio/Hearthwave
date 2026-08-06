import { useEffect, useRef } from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import { formatMessageTime } from '../../utils/datetime';
import { useDayKey } from '../../hooks/useDayKey';

interface Props {
  messages: ChatEntry[];
  /** E-ink wall panels: finalized-only, outlined black-on-white, no animation. */
  eink: boolean;
}

// How far from the top still counts as "reading the newest traffic". Past this
// the operator has scrolled back through history and must not be yanked
// forward when something new arrives.
const STICK_TO_TOP_PX = 24;

// Short direction pill per entry — CW distinguishes morse RX from voice RX.
function badgeLabel(m: ChatEntry): string {
  if (m.kind === 'rx') return m.source === 'cw' ? 'CW' : 'RX';
  if (m.kind === 'tx') return 'TX';
  if (m.kind === 'system') return 'SYS';
  return 'CHAT';
}

// Leading word of the sub-caption; system messages carry only a timestamp.
function captionContext(m: ChatEntry): string {
  if (m.kind === 'rx') return m.source === 'cw' ? 'Morse' : 'Transcribed';
  if (m.kind === 'tx') return 'Voice synthesis';
  if (m.kind === 'chat') return 'Chat';
  return '';
}

// Semantic accent per kind — mirrors the main-app ChatDisplay convention
// (rx=success, tx=info, system=warning, chat=muted) so the product reads
// consistently. E-ink ignores these and uses pure black.
function kindMain(palette: Theme['palette'], kind: ChatEntry['kind']): string {
  switch (kind) {
    case 'rx':
      return palette.success.main;
    case 'tx':
      return palette.info.main;
    case 'system':
      return palette.warning.main;
    default:
      return palette.text.secondary;
  }
}

export function DisplayChatConsole({ messages, eink }: Props) {
  const theme = useTheme();
  // A wall panel runs for weeks — re-render at midnight so yesterday's traffic
  // stops reading as today's.
  useDayKey();
  // E-ink shows finalized text only; partials would fight the slow refresh.
  // Newest first: on a wall panel the eye starts at the top, and it means new
  // traffic never pushes older lines out of view mid-read.
  const shown = (eink ? messages.filter((m) => !m.partial) : messages).slice().reverse();

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const headId = shown[0]?.id;
  useEffect(() => {
    const el = scrollRef.current;
    if (el && el.scrollTop < STICK_TO_TOP_PX) el.scrollTop = 0;
  }, [headId]);

  return (
    <Paper
      component="section"
      aria-label="Radio log"
      sx={{
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        height: '100%',
        minHeight: 0,
        ...(eink ? {} : { boxShadow: 3 }),
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.25,
          px: 2,
          py: 1,
          borderBottom: `1px solid ${theme.palette.divider}`,
          color: 'text.secondary',
        }}
      >
        <Box
          component="i"
          aria-hidden="true"
          sx={
            eink
              ? { width: 10, height: 10, borderRadius: '50%', border: `1px solid ${theme.palette.text.primary}`, flex: 'none' }
              : {
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  flex: 'none',
                  bgcolor: 'warning.main',
                  boxShadow: `0 0 10px ${theme.palette.warning.main}`,
                  animation: 'hw-onair-pulse 3.4s ease-in-out infinite',
                  '@keyframes hw-onair-pulse': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.35 },
                  },
                }
          }
        />
        <Typography sx={{ fontSize: '1.15rem', fontWeight: 600 }}>Radio log</Typography>
        <Typography sx={{ ml: 'auto', fontSize: '0.9rem', color: 'text.secondary' }}>
          newest first
        </Typography>
      </Box>

      <Box
        ref={scrollRef}
        role="log"
        aria-label="Radio log messages"
        aria-live="polite"
        aria-relevant="additions"
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1.5,
          px: 2,
          py: 1.5,
          flexGrow: 1,
          minHeight: 0,
          overflowY: 'auto',
        }}
      >
        {shown.length === 0 && (
          <Typography sx={{ color: 'text.secondary', fontStyle: 'italic', fontSize: '1.1rem' }}>
            No messages yet.
          </Typography>
        )}

        {shown.map((m) => {
          const main = kindMain(theme.palette, m.kind);
          const badgeSx = eink
            ? { color: 'text.primary', border: `1px solid ${theme.palette.text.primary}` }
            : { color: main, bgcolor: alpha(main, 0.16) };
          const context = captionContext(m);
          // Formatted here, not at ingest: a line logged before midnight has to
          // pick up its date once the day rolls over (see useDayKey above).
          const stamp = m.ts ? formatMessageTime(m.ts) : m.timestamp;
          const caption = `${context ? `${context} · ` : ''}${stamp}`;
          const prefix = m.sender && m.recipient ? `${m.sender} → ${m.recipient}` : m.sender;

          return (
            <Box key={m.id} sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start', opacity: m.partial ? 0.7 : 1 }}>
              <Box
                component="span"
                sx={{
                  ...badgeSx,
                  fontFamily: 'monospace',
                  fontSize: '0.9rem',
                  fontWeight: 700,
                  lineHeight: 1.6,
                  px: 1,
                  borderRadius: 1,
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                {badgeLabel(m)}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '1.2rem', lineHeight: 1.35, color: 'text.primary', fontStyle: m.partial ? 'italic' : 'normal' }}>
                  {prefix && (
                    <Box component="span" sx={{ fontWeight: 700 }}>
                      {prefix}:{' '}
                    </Box>
                  )}
                  <Box component="span">{m.text}</Box>
                  {m.partial && !eink && (
                    <Box component="span" sx={{ opacity: 0.5 }}>
                      {' '}
                      …
                    </Box>
                  )}
                </Typography>
                <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', mt: 0.25 }}>{caption}</Typography>
              </Box>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
