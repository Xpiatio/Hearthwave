import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Paper } from '@mui/material';

export interface SpectrogramHandle {
  pushRow: (row: number[], vad?: boolean, squelch?: boolean) => void;
}

interface Props {
  colormap: 'viridis' | 'grayscale';
  timeWindowS: number;
}

const CANVAS_HEIGHT = 128;
// Estimated rows per second from SpectroTask (~20 Hz polling × ~1 frame/poll).
const ROWS_PER_SECOND = 20;
// Width of the VAD/squelch overlay stripes (pixels from left edge).
const STRIPE_W = 4;

// ---------------------------------------------------------------------------
// Colormaps — precomputed LUTs
// ---------------------------------------------------------------------------

type RGB = [number, number, number];

function buildViridisLut(): RGB[] {
  // Key (t, R, G, B) control points for the viridis colormap.
  const kp: [number, number, number, number][] = [
    [0.0,   68,   1,  84],
    [0.13,  72,  40, 120],
    [0.25,  59,  82, 139],
    [0.38,  44, 113, 142],
    [0.5,   33, 145, 140],
    [0.63,  53, 183, 121],
    [0.75,  94, 201,  98],
    [0.88, 174, 220,  41],
    [1.0,  253, 231,  37],
  ];
  const lut: RGB[] = new Array(256);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    let lo = kp[0], hi = kp[kp.length - 1];
    for (let j = 0; j < kp.length - 1; j++) {
      if (t >= kp[j][0] && t <= kp[j + 1][0]) { lo = kp[j]; hi = kp[j + 1]; break; }
    }
    const span = hi[0] - lo[0];
    const s = span > 0 ? (t - lo[0]) / span : 0;
    lut[i] = [
      Math.round(lo[1] + s * (hi[1] - lo[1])),
      Math.round(lo[2] + s * (hi[2] - lo[2])),
      Math.round(lo[3] + s * (hi[3] - lo[3])),
    ];
  }
  return lut;
}

const VIRIDIS_LUT = buildViridisLut();

function applyColormap(val: number, cm: 'viridis' | 'grayscale'): RGB {
  const idx = Math.max(0, Math.min(255, val));
  if (cm === 'grayscale') return [idx, idx, idx];
  return VIRIDIS_LUT[idx];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const Spectrogram = forwardRef<SpectrogramHandle, Props>(
  ({ colormap, timeWindowS }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imageDataRef = useRef<ImageData | null>(null);
    const accRowsRef = useRef<number[][]>([]);
    const accVadRef = useRef(false);
    const accSquelchRef = useRef(false);
    const rowsPerPxRef = useRef(1);

    // Recompute rowsPerPx when timeWindowS changes.
    useEffect(() => {
      rowsPerPxRef.current = Math.max(1, Math.round(ROWS_PER_SECOND * timeWindowS / CANVAS_HEIGHT));
    }, [timeWindowS]);

    // Clear the canvas when colormap or timeWindowS changes.
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      imageDataRef.current = null;
      accRowsRef.current = [];
    }, [colormap, timeWindowS]);

    useImperativeHandle(ref, () => ({
      pushRow(row: number[], vad = false, squelch = false) {
        accRowsRef.current.push(row);
        accVadRef.current = accVadRef.current || vad;
        accSquelchRef.current = accSquelchRef.current || squelch;

        if (accRowsRef.current.length < rowsPerPxRef.current) return;

        // Average the accumulated rows into one canvas row.
        const rows = accRowsRef.current;
        const hadVad = accVadRef.current;
        const hadSquelch = accSquelchRef.current;
        accRowsRef.current = [];
        accVadRef.current = false;
        accSquelchRef.current = false;

        const W = rows[0].length;
        const averaged = new Array<number>(W).fill(0);
        for (const r of rows) {
          for (let x = 0; x < W; x++) averaged[x] += r[x] ?? 0;
        }
        for (let x = 0; x < W; x++) averaged[x] = Math.round(averaged[x] / rows.length);

        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const cW = canvas.width;
        const H = canvas.height;

        if (!imageDataRef.current || imageDataRef.current.width !== cW || imageDataRef.current.height !== H) {
          imageDataRef.current = ctx.createImageData(cW, H);
        }
        const img = imageDataRef.current;

        // Scroll: shift all rows down by one.
        img.data.copyWithin(cW * 4, 0, cW * (H - 1) * 4);

        // Write new row at top.
        for (let x = 0; x < cW; x++) {
          const val = x < averaged.length ? averaged[x] : 0;

          let r: number, g: number, b: number;
          // Overlay stripes on the left edge.
          if (x < STRIPE_W && hadSquelch) {
            // Amber squelch stripe.
            [r, g, b] = [245, 158, 11];
          } else if (x < STRIPE_W && hadVad) {
            // White VAD stripe.
            [r, g, b] = [255, 255, 255];
          } else {
            [r, g, b] = applyColormap(val, colormap);
          }

          const i = x * 4;
          img.data[i]     = r;
          img.data[i + 1] = g;
          img.data[i + 2] = b;
          img.data[i + 3] = 255;
        }

        ctx.putImageData(img, 0, 0);
      },
    }));

    // Initial black fill.
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }, []);

    return (
      <Paper
        square
        elevation={0}
        sx={{
          overflow: 'hidden',
          bgcolor: '#000',
          borderTop: 1,
          borderColor: 'divider',
          lineHeight: 0,
        }}
      >
        <canvas
          ref={canvasRef}
          style={{ display: 'block', width: '100%', height: CANVAS_HEIGHT }}
          width={256}
          height={CANVAS_HEIGHT}
          aria-label="Live audio spectrogram waterfall"
        />
      </Paper>
    );
  }
);

Spectrogram.displayName = 'Spectrogram';
