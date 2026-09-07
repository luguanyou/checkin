import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiClient } from '../api/client';
import { createApi, type AttendanceApi } from '../api/resources';
import type { User } from '../api/types';

type AuthStatus = 'restoring' | 'anonymous' | 'authenticated';
interface AuthContextValue {
  status: AuthStatus; user: User | null; api: AttendanceApi;
  login(username: string, password: string): Promise<User>;
  changePassword(currentPassword: string, newPassword: string): Promise<User>;
  logout(): Promise<void>;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>('restoring');
  const [user, setUser] = useState<User | null>(null);
  const [client] = useState(() => new ApiClient({ onSession: (session) => {
    setUser(session?.user ?? null); setStatus(session ? 'authenticated' : 'anonymous');
  }}));
  const api = useMemo(() => createApi(client), [client]);

  useEffect(() => {
    let active = true;
    api.auth.refresh().then((session) => {
      if (!active) return;
      client.setAccessToken(session.access_token); setUser(session.user); setStatus('authenticated');
    }).catch(() => {
      if (!active) return;
      client.setAccessToken(null); setUser(null); setStatus('anonymous');
    });
    return () => { active = false; };
  }, [api, client]);

  const value = useMemo<AuthContextValue>(() => ({
    status, user, api,
    async login(username, password) {
      const session = await api.auth.login(username, password);
      client.setAccessToken(session.access_token); setUser(session.user); setStatus('authenticated'); return session.user;
    },
    async changePassword(currentPassword, newPassword) {
      const session = await api.auth.changePassword(currentPassword, newPassword);
      client.setAccessToken(session.access_token); setUser(session.user); return session.user;
    },
    async logout() {
      try { await api.auth.logout(); } finally {
        client.setAccessToken(null); setUser(null); setStatus('anonymous'); queryClient.clear();
      }
    },
  }), [api, client, queryClient, status, user]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth 必须在 AuthProvider 内使用'); return value; }
export function useApi() { return useAuth().api; }
