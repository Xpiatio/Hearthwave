import { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Typography, Button, Fab, Chip, Tooltip } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import type { Contact } from '../../types/ws';

export interface ChatEntry {
  id: string;
  timestamp: string;
  kind: 'rx' | 'tx' | 'system';
  sender?: string;
  recipient?: string;   // e.g. "WSLZ233 — Dave"; absent when broadcast to ALL
  text: string;
  speaker?: string;
  partial?: boolean;
  cluster_label?: string | null;
  // Server-computed [start, end, canonical_callsign] tuples — handles NATO phonetic,
  // spaced, hyphenated, and compact forms. Falls back to frontend regex when absent.
  callsign_spans?: Array<[number, number, string]>;
  source?: 'voice' | 'cw';
}

interface Props {
  entries: ChatEntry[];
  contacts: Contact[];
  showCallsignChips: boolean;
  onEnrollCluster?: (clusterLabel: string, callsign: string) => void;
}

// Fallback regex for compact callsign forms when the server hasn't sent spans.
// Matches GMRS modern (WSLZ233), GMRS legacy (KAE1234), US amateur (K1ABC, KD9XYZ).
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
  return parts.join(' · ');
}

interface TextSegment {
  text: string;
  isCallsign: boolean;
  contact?: Contact;
}

// Uses server-provided spans (handles NATO phonetic, spaced, hyphenated, compact forms).
// Each span carries [start, end, canonical_callsign]; the chip shows the canonical form
// while the original matched text (which may be the long NATO spelling) is elided.
function segmentTextBySpans(
  text: string,
  spans: Array<[number, number, string]>,
  callsignIdx: Map<string, Contact>,
): TextSegment[] {
  const segments: TextSegment[] = [];
  let lastIndex = 0;
  for (const [start, end, canonical] of spans) {
    if (start > lastIndex) {
      segments.push({ text: text.slice(lastIndex, start), isCallsign: false });
    }
    segments.push({ text: canonical, isCallsign: true, contact: callsignIdx.get(canonical) });
    lastIndex = end;
  }
  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), isCallsign: false });
  }
  return segments;
}

// Fallback used when the server hasn't sent callsign_spans (compact forms only).
function segmentTextByRegex(text: string, callsignIdx: Map<string, Contact>): TextSegment[] {
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

function CallsignChip({ seg, index }: { seg: TextSegment; index: number }) {
  const chip = (
    <Chip
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
        '& .MuiChip-label': { px: 0.75 },
      }}
    />
  );
  return (
    <span key={index} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 2 }}>
      {seg.contact ? (
        <Tooltip title={callsignTooltip(seg.contact)} placement="top">
          {chip}
        </Tooltip>
      ) : (
        chip
      )}
      {seg.contact?.verified && (
        <Typography component="span" sx={{ fontSize: '0.75rem', color: 'success.main', fontWeight: 700, lineHeight: 1 }}>
          ✓
        </Typography>
      )}
    </span>
  );
}

function MessageText({
  text,
  callsignIdx,
  callsignSpans,
  showCallsignChips,
  color,
}: {
  text: string;
  callsignIdx: Map<string, Contact>;
  callsignSpans?: Array<[number, number, string]>;
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

  const segments = callsignSpans && callsignSpans.length > 0
    ? segmentTextBySpans(text, callsignSpans, callsignIdx)
    : segmentTextByRegex(text, callsignIdx);

  return (
    <Typography component="span" sx={{ wordBreak: 'break-word', color }}>
      {segments.map((seg, i) =>
        seg.isCallsign
          ? <CallsignChip key={i} seg={seg} index={i} />
          : <span key={i}>{seg.text}</span>
      )}
    </Typography>
  );
}

export function ChatDisplay({ entries, contacts, showCallsignChips, onEnrollCluster }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const callsignIdx = useMemo(() => buildCallsignIndex(contacts), [contacts]);

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

            {entry.kind === 'rx' && entry.source !== 'cw' && (
              <Typography
                component="span"
                sx={{ fontWeight: 700, fontSize: '1.0625rem', color: KIND_COLOR.rx, flexShrink: 0 }}
                aria-label="Received from radio"
              >
                [RX]
              </Typography>
            )}
            {entry.kind === 'rx' && entry.source === 'cw' && (
              <Typography
                component="span"
                sx={{ fontWeight: 700, fontSize: '1.0625rem', color: KIND_COLOR.rx, flexShrink: 0 }}
                aria-label="Received morse code"
              >
                [CW]
              </Typography>
            )}
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
                [{entry.sender}]{entry.recipient ? '' : ':'}
              </Typography>
            )}

            {entry.recipient && (
              <Typography
                component="span"
                sx={{ fontWeight: 700, color: KIND_COLOR[entry.kind], flexShrink: 0 }}
              >
                → {entry.recipient}:
              </Typography>
            )}

            <MessageText
              text={entry.text}
              callsignIdx={callsignIdx}
              callsignSpans={entry.callsign_spans}
              showCallsignChips={showCallsignChips && entry.kind === 'rx'}
              color={KIND_COLOR[entry.kind]}
            />
            {entry.partial && (
              <Typography component="span" sx={{ opacity: 0.5, color: KIND_COLOR[entry.kind] }}> …</Typography>
            )}

            {entry.cluster_label && !entry.partial && onEnrollCluster && (
              <Button
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.875rem', py: 0, px: 0.75, minHeight: 0, opacity: 0.7 }}
                onClick={() => {
                  const callsign = window.prompt(`Assign ${entry.cluster_label} to callsign:`);
                  if (callsign?.trim()) {
                    onEnrollCluster(entry.cluster_label!, callsign.trim().toUpperCase());
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
