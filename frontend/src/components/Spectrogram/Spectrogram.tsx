import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import './Spectrogram.css';

export interface SpectrogramHandle {
  pushRow: (row: number[]) => void;
}

const CANVAS_HEIGHT = 96;

function colormap(val: number): [number, number, number] {
  const t = val / 255;
  if (t < 0.5) {
    const s = t * 2;
    return [0, Math.round(s * 200), Math.round(s * 60)];
  }
  const s = (t - 0.5) * 2;
  return [Math.round(s * 255), Math.round(200 + s * 55), Math.round(60 * (1 - s))];
}

export const Spectrogram = forwardRef<SpectrogramHandle>((_, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageDataRef = useRef<ImageData | null>(null);

  useImperativeHandle(ref, () => ({
    pushRow(row: number[]) {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;

      if (!imageDataRef.current || imageDataRef.current.width !== W || imageDataRef.current.height !== H) {
        imageDataRef.current = ctx.createImageData(W, H);
      }
      const img = imageDataRef.current;

      // Scroll existing pixels down by one row
      img.data.copyWithin(W * 4, 0, W * (H - 1) * 4);

      // Write new row at the top
      for (let x = 0; x < W; x++) {
        const val = x < row.length ? row[x] : 0;
        const [r, g, b] = colormap(val);
        const i = x * 4;
        img.data[i] = r;
        img.data[i + 1] = g;
        img.data[i + 2] = b;
        img.data[i + 3] = 255;
      }

      ctx.putImageData(img, 0, 0);
    },
  }));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }, []);

  return (
    <div className="spectrogram-wrap">
      <canvas
        ref={canvasRef}
        className="spectrogram-canvas"
        width={256}
        height={CANVAS_HEIGHT}
        aria-label="Live audio spectrogram waterfall"
      />
    </div>
  );
});

Spectrogram.displayName = 'Spectrogram';
