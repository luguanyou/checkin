import { StrictMode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './auth';

function SessionState() {
  const { status, user } = useAuth();
  return <div role="status">{status}:{user?.display_name}</div>;
}

afterEach(() => vi.unstubAllGlobals());

it('restores a rotating refresh session only once when StrictMode replays effects', async () => {
  let refreshCount = 0;
  const fetcher = vi.fn(async () => {
    refreshCount += 1;
    // A real refresh token is consumed and rotated on the first request.
    const accepted = refreshCount === 1;
    return new Response(JSON.stringify(accepted ? {
      access_token: 'test-access-token', token_type: 'bearer', expires_in: 900,
      user: { id: 'teacher', username: 'teacher', display_name: '王老师', role: 'TEACHER', status: 'ACTIVE', must_change_password: false },
    } : { code: 'AUTHENTICATION_REQUIRED', message: '请先登录', details: {}, request_id: 'test' }), {
      status: accepted ? 200 : 401, headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetcher);
  render(<StrictMode><QueryClientProvider client={new QueryClient()}><AuthProvider><SessionState /></AuthProvider></QueryClientProvider></StrictMode>);
  await waitFor(() => expect(screen.getByRole('status')).not.toHaveTextContent('restoring'));
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('status')).toHaveTextContent('authenticated:王老师');
});
