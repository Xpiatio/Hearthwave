import { describe, it, expect } from 'vitest';
import { streamMsgToEntry } from '../App';
import type { StoredStreamMsg } from '../types/ws';

// streamMsgToEntry maps a backfilled chat_history entry to a ChatEntry. The
// chat_history handler is just `messages.map(streamMsgToEntry)` and chat_cleared
// just empties the list, so covering the mapper covers the backfill behaviour.
describe('streamMsgToEntry', () => {
  it('maps a chat_echo to a chat entry, preferring display_name as sender', () => {
    const msg = {
      type: 'chat_echo', ts: '2026-06-16T12:00:00Z',
      display_name: 'Bob', operator: 'op', callsign: 'W5TST', text: 'hi all',
    } as StoredStreamMsg;
    const e = streamMsgToEntry(msg);
    expect(e.kind).toBe('chat');
    expect(e.sender).toBe('Bob');
    expect(e.text).toBe('hi all');
    expect(e.id).toBeTruthy();
  });

  it('falls back to operator then callsign when display_name is empty', () => {
    const e = streamMsgToEntry({
      type: 'chat_echo', ts: 't', display_name: '', operator: '', callsign: 'W5TST', text: 'x',
    } as StoredStreamMsg);
    expect(e.sender).toBe('W5TST');
  });

  it('maps a directed tx_echo to a tx entry with a recipient label', () => {
    const e = streamMsgToEntry({
      type: 'tx_echo', ts: 't', callsign: 'W5TST', operator: 'Op', display_name: 'Bob',
      text: 'come back', target_call: 'K0BOB', target_name: 'Bob Jones',
    } as StoredStreamMsg);
    expect(e.kind).toBe('tx');
    expect(e.sender).toBe('Bob');
    expect(e.recipient).toBe('K0BOB — Bob Jones');
  });

  it('leaves recipient undefined for an ALL tx_echo', () => {
    const e = streamMsgToEntry({
      type: 'tx_echo', ts: 't', callsign: 'W5TST', operator: 'Op', display_name: 'Bob',
      text: 'cq', target_call: 'ALL', target_name: '',
    } as StoredStreamMsg);
    expect(e.recipient).toBeUndefined();
  });

  it('maps an rx_message to an rx entry carrying callsign spans and source', () => {
    const e = streamMsgToEntry({
      type: 'rx_message', ts: 't', from: '', callsign: '', text: 'roger that',
      utterance_id: 'u1', partial: false,
      callsign_spans: [[0, 5, 'W5TST']], source: 'voice',
    } as StoredStreamMsg);
    expect(e.kind).toBe('rx');
    expect(e.text).toBe('roger that');
    expect(e.callsign_spans).toEqual([[0, 5, 'W5TST']]);
    expect(e.source).toBe('voice');
  });

  it('assigns distinct ids across successive entries', () => {
    const mk = () => streamMsgToEntry({
      type: 'chat_echo', ts: 't', display_name: 'A', operator: '', callsign: '', text: 'x',
    } as StoredStreamMsg);
    expect(mk().id).not.toBe(mk().id);
  });
});
