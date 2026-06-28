import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Paper } from '@mui/material';

export interface AudioLevelMeterHandle {
  /** Feed a spectrogram row (256 uint8 bins, 0..255). Drives the bar level. */
  pushRow: (row: number[]) => void;
}

// Physical canvas size; CSS stretches the canvas to the container width.
const CANVAS_WIDTH = 512;
const CANVAS_HEIGHT = 16;

// Per-frame (~60fps) smoothing — fast rise, slow fall, VU-style.
const ATTACK = 0.5;
const RELEASE = 0.08;
// Target decays each frame so the bar falls to zero if the row stream halts.
const TARGET_DECAY = 0.05;
// Peak-hold marker decay per frame.
const PEAK_DECAY = 0.012;

// Brand gradient (cyan → violet → magenta), matching components/Logo/Logo.tsx.
const GRAD_STOPS: ReadonlyArray<readonly [number, string]> = [
  [0, '#36DDE4'],
  [0.5, '#8B5CF6'],
  [1, '#EA53C6'],
];

/**
 * Peak bin of a spectrogram row mapped to a 0..1 level. Rows are dB-scaled
 * uint8 values (0 = −120 dBFS, 255 = 0 dBFS), so the peak bin is a responsive,
 * already-logarithmic "audio present" indicator.
 */
export function peakLevel(row: number[]): number {
  let max = 0;
  for (let i = 0; i < row.length; i++) {
    const v = row[i] ?? 0;
    if (v > max) max = v;
  }
  return Math.max(0, Math.min(1, max / 255));
}

export const AudioLevelMeter = forwardRef<AudioLevelMeterHandle, object>(
  (_props, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const targetRef = useRef(0); // latest peak from pushRow (0..1)
    const levelRef = useRef(0); // smoothed displayed level
    const peakHoldRef = useRef(0); // decaying peak marker

    useImperativeHandle(ref, () => ({
      pushRow(row: number[]) {
        targetRef.current = peakLevel(row);
      },
    }));

    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;
      const grad = ctx.createLinearGradient(0, 0, W, 0);
      for (const [stop, color] of GRAD_STOPS) grad.addColorStop(stop, color);

      let raf = 0;
      const draw = () => {
        const target = targetRef.current;
        // Fast attack when rising, slow release when falling.
        const coef = target > levelRef.current ? ATTACK : RELEASE;
        levelRef.current += (target - levelRef.current) * coef;
        // Decay the target so a halted row stream drops the bar to zero.
        targetRef.current = target * (1 - TARGET_DECAY);

        const level = levelRef.current;
        peakHoldRef.current =
          level > peakHoldRef.current
            ? level
            : Math.max(0, peakHoldRef.current - PEAK_DECAY);

        ctx.clearRect(0, 0, W, H);
        // Track background.
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.fillRect(0, 0, W, H);

        // Filled level bar.
        const fillW = Math.round(level * W);
        if (fillW > 0) {
          ctx.fillStyle = grad;
          ctx.fillRect(0, 0, fillW, H);
        }

        // Peak-hold tick.
        if (peakHoldRef.current > 0.001) {
          const px = Math.min(W - 2, Math.round(peakHoldRef.current * W));
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.fillRect(px, 0, 2, H);
        }

        raf = requestAnimationFrame(draw);
      };
      raf = requestAnimationFrame(draw);
      return () => cancelAnimationFrame(raf);
    }, []);

    return (
      <Paper
        square
        elevation={0}
        sx={{
          flexShrink: 0,
          width: '100%',
          height: 16,
          overflow: 'hidden',
          // canvas background is intentionally black for level-bar contrast
          bgcolor: '#000',
          borderBottom: 1,
          borderColor: 'divider',
          lineHeight: 0,
        }}
      >
        <canvas
          ref={canvasRef}
          role="img"
          style={{ display: 'block', width: '100%', height: '100%' }}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          aria-label="RX audio level meter"
        />
      </Paper>
    );
  },
);

AudioLevelMeter.displayName = 'AudioLevelMeter';
