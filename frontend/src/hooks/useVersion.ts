import { useEffect, useState } from 'react';

/**
 * Fetches the running backend version from the unauthenticated /health
 * endpoint once on mount. Returns null until it resolves (or on failure).
 */
export function useVersion(): string | null {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/health')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.version === 'string') {
          setVersion(data.version);
        }
      })
      .catch(() => {
        /* leave version null — the UI shows a graceful fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return version;
}
