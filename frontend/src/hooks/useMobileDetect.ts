import { useMemo } from 'react';

export function useMobileDetect(): boolean {
  return useMemo(() => (
    window.matchMedia('(pointer: coarse)').matches ||
    window.matchMedia('(max-width: 600px)').matches
  ), []);
}
