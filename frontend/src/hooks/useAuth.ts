import { useState, useEffect, useCallback } from 'react';
import type { UserProfile } from '../types/ws';

const TOKEN_KEY = 'auth_token';

export interface AuthError {
  status: number;
  detail: string;
}

export interface SetupData {
  display_name: string;
  password: string;
  avatar_emoji?: string;
  operator_name?: string;
  callsign?: string;
  location?: string;
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [setupNeeded, setSetupNeeded] = useState(false);
  // true while validating an existing token on page load
  const [loading, setLoading] = useState(true);

  // On mount: check setup status, then validate existing token if present
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);

    fetch('/auth/setup-status')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.setup_needed) {
          setSetupNeeded(true);
          return;
        }
        if (!stored) return;
        return fetch('/auth/me', { headers: { Authorization: `Bearer ${stored}` } })
          .then((r) => (r.ok ? r.json() : null))
          .then((p: UserProfile | null) => {
            if (p) {
              setToken(stored);
              setProfile(p);
            } else {
              localStorage.removeItem(TOKEN_KEY);
              setToken(null);
            }
          });
      })
      .catch(() => {
        // Network error: keep token but don't validate — WS will fail if truly invalid.
      })
      .finally(() => setLoading(false));
  }, []);

  const setup = useCallback(async (data: SetupData): Promise<UserProfile> => {
    const r = await fetch('/auth/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await r.json();
    if (!r.ok) {
      const err: AuthError = { status: r.status, detail: json.detail ?? 'Setup failed' };
      throw err;
    }
    localStorage.setItem(TOKEN_KEY, json.token);
    setToken(json.token);
    setProfile(json.profile);
    setSetupNeeded(false);
    return json.profile as UserProfile;
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

  return { token, profile, setProfile, loading, setupNeeded, setup, login, logout };
}
