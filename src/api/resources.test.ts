import { describe, expect, it, vi } from 'vitest';
import { ApiClient } from './client';
import { createApi } from './resources';

function jsonResponse(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('administrator user resources', () => {
  it('maps list filters to the administrator endpoint', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => (
      jsonResponse({ items: [], page: 2, page_size: 20, total: 0 })
    ));
    const api = createApi(new ApiClient({ baseUrl: '/api/v1', fetcher }));

    await api.adminUsers.list({ page: 2, page_size: 20, role: 'TEACHER', status: 'ACTIVE', q: 'wang' });

    const url = new URL(String(fetcher.mock.calls[0]?.[0]), 'https://test.local');
    expect(url.pathname).toBe('/api/v1/admin/users');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      page: '2', page_size: '20', role: 'TEACHER', status: 'ACTIVE', q: 'wang',
    });
  });

  it('maps teacher account mutations to their exact request contracts', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => (
      String(input).endsWith('/reset-password') ? jsonResponse(null, 204) : jsonResponse({})
    ));
    const api = createApi(new ApiClient({ baseUrl: '/api/v1', fetcher }));

    await api.adminUsers.create({
      username: 'wang01', display_name: '王老师', temporary_password: 'temporary-1234',
    });
    await api.adminUsers.updateStatus('teacher-1', 'DISABLED');
    await api.adminUsers.resetPassword('teacher-1', 'replacement-1234');

    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/v1/admin/users', expect.objectContaining({
      method: 'POST', body: JSON.stringify({
        username: 'wang01', display_name: '王老师', temporary_password: 'temporary-1234',
      }),
    }));
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/v1/admin/users/teacher-1/status', expect.objectContaining({
      method: 'PATCH', body: JSON.stringify({ status: 'DISABLED' }),
    }));
    expect(fetcher).toHaveBeenNthCalledWith(3, '/api/v1/admin/users/teacher-1/reset-password', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ temporary_password: 'replacement-1234' }),
    }));
  });
});

describe('course resources', () => {
  it('maps course and class updates and deletes to their endpoints', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({}, 204));
    const api = createApi(new ApiClient({ baseUrl: '/api/v1', fetcher }));

    await api.courses.update('course-1', { name: '新课程' });
    await api.courses.updateClass('class-1', { name: '新班级' });
    await api.courses.delete('course-1');
    await api.courses.deleteClass('class-1');

    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/v1/courses/course-1', expect.objectContaining({
      method: 'PATCH', body: JSON.stringify({ name: '新课程' }),
    }));
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/v1/classes/class-1', expect.objectContaining({
      method: 'PATCH', body: JSON.stringify({ name: '新班级' }),
    }));
    expect(fetcher).toHaveBeenNthCalledWith(3, '/api/v1/courses/course-1', expect.objectContaining({ method: 'DELETE' }));
    expect(fetcher).toHaveBeenNthCalledWith(4, '/api/v1/classes/class-1', expect.objectContaining({ method: 'DELETE' }));
  });
});
