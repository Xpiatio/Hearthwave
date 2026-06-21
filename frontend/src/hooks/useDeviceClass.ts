import { useEffect, useState } from 'react';

export type DeviceClass = 'phone' | 'tablet' | 'desktop';

const PHONE_Q = '(pointer: coarse) and (max-width: 600px)';
const TABLET_Q = '(pointer: coarse) and (min-width: 601px) and (max-width: 1200px)';

function classify(): DeviceClass {
  if (window.matchMedia(PHONE_Q).matches) return 'phone';
  if (window.matchMedia(TABLET_Q).matches) return 'tablet';
  return 'desktop';
}

export function useDeviceClass(): DeviceClass {
  const [deviceClass, setDeviceClass] = useState<DeviceClass>(() => classify());

  useEffect(() => {
    const queries = [PHONE_Q, TABLET_Q].map((q) => window.matchMedia(q));
    const onChange = () => setDeviceClass(classify());
    queries.forEach((mql) => mql.addEventListener('change', onChange));
    onChange(); // resync in case it changed before listeners attached
    return () => queries.forEach((mql) => mql.removeEventListener('change', onChange));
  }, []);

  return deviceClass;
}
