import { useState, useRef, useEffect } from 'react';
import { Button, Tooltip } from '@mui/material';

interface VoicePTTProps {
  disabled: boolean;
  onStart:  () => void;
  onChunk:  (b64: string) => void;
  onEnd:    () => void;
  onCancel: () => void;
}

const WORKLET_CODE = `
class PcmChunker extends AudioWorkletProcessor {
  constructor() { super(); this._buf = []; this._target = 4096; }
  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) this._buf.push(ch[i]);
    while (this._buf.length >= this._target) {
      this.port.postMessage(new Float32Array(this._buf.splice(0, this._target)));
    }
    return true;
  }
}
registerProcessor('pcm-chunker', PcmChunker);
`;

function float32ToInt16(f: Float32Array): Int16Array {
  const o = new Int16Array(f.length);
  for (let i = 0; i < f.length; i++) o[i] = Math.max(-32768, Math.min(32767, f[i] * 32768));
  return o;
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}

export function VoicePTT({ disabled, onStart, onChunk, onEnd, onCancel }: VoicePTTProps) {
  const [recording, setRecording]               = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef  = useRef<AudioWorkletNode | null>(null);
  const streamRef   = useRef<MediaStream | null>(null);
  const activeRef   = useRef(false);

  const startRecording = async () => {
    if (disabled || activeRef.current) return;
    activeRef.current = true;
    setRecording(true);

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (err) {
      const name = (err as DOMException).name;
      if (name === 'NotAllowedError' || name === 'NotFoundError') {
        setPermissionDenied(true);
      }
      activeRef.current = false;
      setRecording(false);
      onCancel();
      return;
    }

    streamRef.current = stream;

    const ctx = new AudioContext({ sampleRate: 16000 });
    audioCtxRef.current = ctx;

    const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
    const url  = URL.createObjectURL(blob);
    await ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);

    const source = ctx.createMediaStreamSource(stream);
    const node   = new AudioWorkletNode(ctx, 'pcm-chunker');

    node.port.onmessage = (e: MessageEvent<Float32Array>) => {
      const int16 = float32ToInt16(e.data);
      onChunk(arrayBufferToBase64(int16.buffer as ArrayBuffer));
    };

    source.connect(node);
    workletRef.current = node;

    onStart();
  };

  const stopRecording = (cancel = false) => {
    if (!activeRef.current) return;
    activeRef.current = false;
    setRecording(false);

    workletRef.current?.port.close();
    workletRef.current?.disconnect();
    workletRef.current = null;

    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;

    audioCtxRef.current?.close();
    audioCtxRef.current = null;

    if (cancel) {
      onCancel();
    } else {
      onEnd();
    }
  };

  // Cancel if disabled flips on while recording (WS drop, listen-only toggle)
  useEffect(() => {
    if (disabled && activeRef.current) stopRecording(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);

  // Cleanup on unmount
  useEffect(() => () => { if (activeRef.current) stopRecording(true); }, []);

  return (
    <Tooltip title={permissionDenied ? 'Microphone access denied' : recording ? 'Release to transmit' : 'Hold to talk'}>
      <span>
        <Button
          variant={recording ? 'contained' : 'outlined'}
          color={recording ? 'error' : 'inherit'}
          size="small"
          disabled={disabled}
          onMouseDown={startRecording}
          onMouseUp={() => stopRecording(false)}
          onMouseLeave={() => { if (recording) stopRecording(false); }}
          onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
          onTouchEnd={(e) => { e.preventDefault(); stopRecording(false); }}
          sx={{ fontFamily: 'monospace', fontWeight: 700 }}
        >
          {recording ? 'PTT●' : 'PTT'}
        </Button>
      </span>
    </Tooltip>
  );
}
