import { useEffect, useRef, useState } from 'react';
import { Box, Typography, Button, Fab, Chip, Tooltip } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import type { Contact } from '../../types/ws';

export interface ChatEntry {
  id: string;
  timestamp: string;
  kind: 'rx' | 'tx' | 'system';
  sender?: string;
  text: string;
  speaker?: string;
  partial?: boolean;
  cluster_label?: string | null;
  onEnrollCluster?: (clusterLabel: string, callsign: string) => void;
}

interface Props {
  entries: ChatEntry[];
  contacts: Contact[];
  showCallsignChips: boolean;
}

// Matches GMRS modern (WSLZ233), GMRS legacy (KAE1234), and US amateur (K1ABC, KD9XYZ)
const CALLSIGN_RE = /\b(W[A-Z]{3}\d{3}|KA[A-Z]\d{3,4}|[AKNW][A-Z]?\d[A-Z]{1,3})\b/gi;

const KIND_COLOR: Record<string, string> = {
  rx: 'success.main',
  tx: 'info.main',
  system: 'warning.main',
};

const SCROLL_THRESHOLD = 80;

function buildCallsignIndex(contacts: Contact[]): Map<string, Contact> {
  const idx = new Map<string, Contact>();
  for (const c of contacts) {
    idx.set(c.callsign.toUpperCase(), c);
    if (c.gmrs_callsign) idx.set(c.gmrs_callsign.toUpperCase(), c);
    if (c.ham_callsign) idx.set(c.ham_callsign.toUpperCase(), c);
  }
  return idx;
}

function callsignTooltip(c: Contact): string {
  const parts = [c.callsign];
  if (c.name) parts.push(c.name);
  if (c.location) parts.push(c.location);
  if (c.gmrs_callsign && c.gmrs_callsign !== c.callsign) parts.push(`GMRS: ${c.gmrs_callsign}`);
  if (c.ham_callsign && c.ham_callsign !== c.callsign) parts.push(`HAM: ${c.ham_callsign}`);
  if (c.verified) parts.push('✓ Verified');
  return parts.join(' · ');
}

interface TextSegment {
  text: string;
  isCallsign: boolean;
  contact?: Contact;
}

function segmentText(text: string, callsignIdx: Map<string, Contact>): TextSegment[] {
  const segments: TextSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  CALLSIGN_RE.lastIndex = 0;
  while ((match = CALLSIGN_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ text: text.slice(lastIndex, match.index), isCallsign: false });
    }
    const cs = match[0].toUpperCase();
    segments.push({ text: match[0], isCallsign: true, contact: callsignIdx.get(cs) });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), isCallsign: false });
  }
  return segments;
}

function MessageText({
  text,
  callsignIdx,
  showCallsignChips,
  color,
}: {
  text: string;
  callsignIdx: Map<string, Contact>;
  showCallsignChips: boolean;
  color: string;
}) {
  if (!showCallsignChips) {
    return (
      <Typography component="span" sx={{ wordBreak: 'break-word', color }}>
        {text}
      </Typography>
    );
  }

  const segments = segmentText(text, callsignIdx);

  return (
    <Typography component="span" sx={{ wordBreak: 'break-word', color }}>
      {segments.map((seg, i) => {
        if (!seg.isCallsign) return <span key={i}>{seg.text}</span>;
        const chip = (
          <Chip
            key={i}
            label={seg.text}
            size="small"
            sx={{
              mx: 0.25,
              height: 20,
              fontSize: '0.875rem',
              fontFamily: 'monospace',
              fontWeight: 700,
              bgcolor: seg.contact ? 'warning.light' : 'action.hover',
              color: seg.contact ? 'warning.dark' : 'text.secondary',
              cursor: seg.contact ? 'default' : 'default',
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        );
        if (seg.contact) {
          return (
            <Tooltip key={i} title={callsignTooltip(seg.contact)} placement="top">
              {chip}
            </Tooltip>
          );
        }
        return chip;
      })}
    </Typography>
  );
}

export function ChatDisplay({ entries, contacts, showCallsignChips }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const callsignIdx = buildCallsignIndex(contacts);

  function handleScroll() {
    const el = containerRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    atBottomRef.current = distFromBottom < SCROLL_THRESHOLD;
    setShowScrollBtn(distFromBottom >= SCROLL_THRESHOLD);
  }

  function scrollToBottom() {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  useEffect(() => {
    if (atBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [entries]);

  return (
    <Box sx={{ flex: '1 1 auto', position: 'relative', overflow: 'hidden' }}>
      <Box
        component="main"
        ref={containerRef}
        onScroll={handleScroll}
        aria-label="Message history"
        aria-live="polite"
        aria-relevant="additions"
        sx={{
          height: '100%',
          overflowY: 'auto',
          px: 2,
          py: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
        }}
      >
        {entries.length === 0 && (
          <Typography
            sx={{ color: 'text.secondary', fontStyle: 'italic', fontSize: '1.125rem', m: 'auto', textAlign: 'center' }}
          >
            No messages yet. Waiting for radio traffic...
          </Typography>
        )}

        {entries.map((entry) => (
          <Box
            key={entry.id}
            sx={{
              fontSize: '1.25rem',
              lineHeight: 1.5,
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'baseline',
              gap: '0.3rem',
              opacity: entry.partial ? 0.75 : 1,
            }}
          >
            <Typography
              component="span"
              variant="body2"
              sx={{
                fontVariantNumeric: 'tabular-nums',
                color: 'text.secondary',
                fontSize: '1.0625rem',
                flexShrink: 0,
              }}
            >
              {entry.timestamp}
            </Typography>

            {entry.kind === 'tx' && (
              <Typography
                component="span"
                sx={{ fontWeight: 700, fontSize: '1.0625rem', color: KIND_COLOR.tx, flexShrink: 0 }}
                aria-label="Sent by you"
              >
                [TX]
              </Typography>
            )}
            {entry.kind === 'system' && (
              <Typography
                component="span"
                sx={{ fontWeight: 700, fontSize: '1.0625rem', color: KIND_COLOR.system, flexShrink: 0 }}
                aria-label="System message"
              >
                [SYS]
              </Typography>
            )}

            {entry.speaker && (
              <Typography
                component="span"
                sx={{ fontSize: '0.9375rem', color: 'text.secondary', flexShrink: 0 }}
              >
                [{entry.speaker}]
              </Typography>
            )}

            {entry.sender && (
              <Typography
                component="span"
                sx={{ fontWeight: 700, color: KIND_COLOR[entry.kind], flexShrink: 0 }}
              >
                [{entry.sender}]:
              </Typography>
            )}

            <MessageText
              text={entry.text}
              callsignIdx={callsignIdx}
              showCallsignChips={showCallsignChips && entry.kind === 'rx'}
              color={KIND_COLOR[entry.kind]}
            />
            {entry.partial && (
              <Typography component="span" sx={{ opacity: 0.5, color: KIND_COLOR[entry.kind] }}> …</Typography>
            )}

            {entry.cluster_label && !entry.partial && entry.onEnrollCluster && (
              <Button
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.875rem', py: 0, px: 0.75, minHeight: 0, opacity: 0.7 }}
                onClick={() => {
                  const callsign = window.prompt(`Assign ${entry.cluster_label} to callsign:`);
                  if (callsign?.trim()) {
                    entry.onEnrollCluster!(entry.cluster_label!, callsign.trim().toUpperCase());
                  }
                }}
              >
                Identify {entry.cluster_label}
              </Button>
            )}
          </Box>
        ))}

        <div ref={bottomRef} aria-hidden="true" />
      </Box>

      {showScrollBtn && (
        <Fab
          size="small"
          color="primary"
          onClick={scrollToBottom}
          aria-label="Scroll to latest message"
          sx={{ position: 'absolute', bottom: 16, right: 16, zIndex: 1 }}
        >
          <KeyboardArrowDownIcon />
        </Fab>
      )}
    </Box>
  );
}
