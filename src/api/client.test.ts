import { describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, parseDownloadFilename } from './client';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiClient', () => {
  it('adds the bearer token and parses JSON', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ value: 42 }));
    const client = new ApiClient({ fetcher });
    client.setAccessToken('access-token');

    await expect(client.request<{ value: number }>('/courses')).resolves.toEqual({ value: 42 });
    const [, init] = fetcher.mock.calls[0];
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer access-token');
    expect(init?.credentials).toBe('include');
  });

  it('converts the uniform API error into ApiError', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({
      code: 'INVALID_REQUEST',
      message: '请求无效',
      details: { field: 'name' },
      request_id: 'request-1',
    }, 400));
    const client = new ApiClient({ fetcher });

    const error = await client.request('/courses').catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 400, code: 'INVALID_REQUEST', requestId: 'request-1' });
  });

  it('shares one refresh across concurrent unauthorized responses', async () => {
    let token = 'expired';
    let refreshes = 0;
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) {
        refreshes += 1;
        await Promise.resolve();
        token = 'fresh';
        return jsonResponse({ access_token: token, user: { id: 'u1' } });
      }
      const authorization = new Headers(init?.headers).get('Authorization');
      return authorization === 'Bearer fresh'
        ? jsonResponse({ ok: true })
        : jsonResponse({ code: 'AUTHENTICATION_REQUIRED', message: '请先登录', details: {}, request_id: 'r' }, 401);
    });
    const client = new ApiClient({ fetcher });
    client.setAccessToken(token);

    await expect(Promise.all([client.request('/courses'), client.request('/attendance-sessions')]))
      .resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(refreshes).toBe(1);
    expect(client.getAccessToken()).toBe('fresh');
  });

  it('does not retry when refresh also fails', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({
      code: 'AUTHENTICATION_REQUIRED', message: '请先登录', details: {}, request_id: 'r',
    }, 401));
    const client = new ApiClient({ fetcher });

    await expect(client.request('/courses')).rejects.toMatchObject({ status: 401 });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('does not set JSON content type for FormData', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ preview_id: 'p1' }));
    const client = new ApiClient({ fetcher });
    const form = new FormData();
    form.append('file', new File(['a'], 'roster.csv'));

    await client.request('/classes/c1/roster/import-preview', { method: 'POST', body: form });
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has('Content-Type')).toBe(false);
  });

  it('returns a blob with the decoded server filename', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response('csv', {
      headers: { 'Content-Disposition': "attachment; filename*=UTF-8''%E8%80%83%E5%8B%A4.csv" },
    }));
    const client = new ApiClient({ fetcher });

    const result = await client.download('/attendance-sessions/s1/export?format=csv');
    expect(result.filename).toBe('考勤.csv');
    expect(await result.blob.text()).toBe('csv');
  });
});

describe('parseDownloadFilename', () => {
  it('falls back when content disposition is absent or unsafe', () => {
    expect(parseDownloadFilename(null)).toBe('attendance-export');
    expect(parseDownloadFilename('attachment; filename="../report.csv"')).toBe('report.csv');
  });
});
