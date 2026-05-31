import { useState, useEffect, useCallback } from 'react';
import type { UserProfile } from '../types/ws';

const TOKEN_KEY = 'auth_token';

export interface AuthError {
  status: number;
  detail: string;
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [profile, setProfile] = useState<UserProfile | null>(null);
  // true while validating an existing token on page load
  const [loading, setLoading] = useState(true);

  // On mount: validate existing token against /auth/me
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    fetch('/auth/me', { headers: { Authorization: `Bearer ${stored}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((p: UserProfile | null) => {
        if (p) {
          setToken(stored);
          setProfile(p);
        } else {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      })
      .catch(() => {
        // Network error: keep token but don't validate — WS will fail if truly invalid.
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (displayName: string, password: string): Promise<UserProfile> => {
    const r = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: displayName, password }),
    });
    const data = await r.json();
    if (!r.ok) {
      const err: AuthError = { status: r.status, detail: data.detail ?? 'Login failed' };
      throw err;
    }
    localStorage.setItem(TOKEN_KEY, data.token);
    setToken(data.token);
    setProfile(data.profile);
    return data.profile as UserProfile;
  }, []);

  const logout = useCallback(async () => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (t) {
      await fetch('/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${t}` },
      }).catch(() => {});
    }
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setProfile(null);
  }, []);

  return { token, profile, setProfile, loading, login, logout };
}
