import { useDeviceClass } from './useDeviceClass';

export function useMobileDetect(): boolean {
  return useDeviceClass() === 'phone';
}
