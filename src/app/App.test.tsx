import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { queryClient } from './query-client';

function errorResponse() {
  return new Response(JSON.stringify({
    code: 'AUTHENTICATION_REQUIRED', message: '请先登录', details: {}, request_id: 'r1',
  }), { status: 401, headers: { 'Content-Type': 'application/json' } });
}

function sessionResponse(role: 'ADMIN' | 'TEACHER') {
  return new Response(JSON.stringify({
    access_token: 'access-token',
    token_type: 'bearer',
    expires_in: 900,
    user: {
      id: `${role.toLowerCase()}-id`,
      username: role === 'ADMIN' ? 'admin' : 'teacher01',
      display_name: role === 'ADMIN' ? '系统管理员' : '王老师',
      role,
      status: 'ACTIVE',
      must_change_password: false,
      last_login_at: null,
      created_at: '2026-09-03T00:00:00Z',
      updated_at: '2026-09-03T00:00:00Z',
    },
  }), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

function emptyPageResponse() {
  return new Response(JSON.stringify({ items: [], page: 1, page_size: 20, total: 0 }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    queryClient.clear();
    window.history.replaceState({}, '', '/');
  });

  it('shows login after session restoration fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      code: 'AUTHENTICATION_REQUIRED', message: '请先登录', details: {}, request_id: 'r1',
    }), { status: 401, headers: { 'Content-Type': 'application/json' } })));
    render(<App />);
    expect(screen.getByText('正在恢复登录状态...')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: '登录课点' })).toBeInTheDocument();
  });

  it('validates login fields before sending a request', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({
      code: 'AUTHENTICATION_REQUIRED', message: '请先登录', details: {}, request_id: 'r1',
    }), { status: 401, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    await screen.findByRole('heading', { name: '登录课点' });
    await userEvent.click(screen.getByRole('button', { name: '登录' }));
    expect(screen.getByText('请输入用户名')).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('submits a non-empty legacy short password', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      code: 'INVALID_CREDENTIALS', message: '用户名或密码错误', details: {}, request_id: 'r1',
    }), { status: 401, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    await screen.findByRole('heading', { name: '登录课点' });

    await userEvent.type(screen.getByLabelText('用户名'), 'admin');
    await userEvent.type(screen.getByLabelText('密码'), 'short-pass');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[1]?.body).toBe(JSON.stringify({
      username: 'admin', password: 'short-pass',
    }));
  });

  it('routes an administrator to its page without teacher requests', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) return errorResponse();
      if (url.endsWith('/auth/login')) return sessionResponse('ADMIN');
      if (url.includes('/admin/users')) return emptyPageResponse();
      return new Response(null, { status: 500 });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    await screen.findByRole('heading', { name: '登录课点' });

    await userEvent.type(screen.getByLabelText('用户名'), 'admin');
    await userEvent.type(screen.getByLabelText('密码'), 'configured-admin-password');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    expect(await screen.findByRole('heading', { name: '教师账号' })).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/admin');
    expect(fetcher).toHaveBeenCalledTimes(6);
    expect(fetcher.mock.calls.some(([input]) => /courses|attendance/.test(String(input)))).toBe(false);
  });

  it('redirects a restored administrator away from the teacher dashboard', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => (
      String(input).includes('/admin/users') ? emptyPageResponse() : sessionResponse('ADMIN')
    ));
    vi.stubGlobal('fetch', fetcher);
    render(<App />);

    expect(await screen.findByRole('heading', { name: '教师账号' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/admin');
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(5));
  });

  it('redirects a teacher away from the administrator page', async () => {
    window.history.replaceState({}, '', '/admin');
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) return sessionResponse('TEACHER');
      return emptyPageResponse();
    });
    vi.stubGlobal('fetch', fetcher);
    render(<App />);

    expect(await screen.findByRole('heading', { name: '工作台' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
  });

  it('logs out from the administrator page', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) return sessionResponse('ADMIN');
      if (url.endsWith('/auth/logout')) return new Response(null, { status: 204 });
      if (url.includes('/admin/users')) return emptyPageResponse();
      return new Response(null, { status: 500 });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    await screen.findByRole('heading', { name: '教师账号' });

    await userEvent.click(screen.getByRole('button', { name: '退出登录' }));

    expect(await screen.findByRole('heading', { name: '登录课点' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/login');
  });

  it('allows teachers to open scores and keeps administrators out of the teacher module', async () => {
    window.history.replaceState({}, '', '/scores');
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/auth/refresh') ? sessionResponse('TEACHER') : emptyPageResponse());
    vi.stubGlobal('fetch', fetcher);
    const view = render(<App />);
    expect(await screen.findByRole('heading', { name: '平时成绩' })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: '还没有可用班级' })).toBeInTheDocument();
    view.unmount(); queryClient.clear();
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/auth/refresh') ? sessionResponse('ADMIN') : emptyPageResponse()));
    render(<App />);
    expect(await screen.findByRole('heading', { name: '教师账号' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/admin');
  });
});
