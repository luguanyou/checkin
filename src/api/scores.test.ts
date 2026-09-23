import { describe, expect, it, vi } from 'vitest';
import { ApiClient } from './client';
import { createApi } from './resources';

describe('scores contracts', () => {
  it('preserves fractional, zero and unevaluated values and sends version for atomic writes', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response('{}', { headers: { 'Content-Type': 'application/json' } }));
    const api = createApi(new ApiClient({ baseUrl: '/api/v1', fetcher }));
    const records = [{ enrollment_id: 'e1', points: '-0.5', note: '提醒' }, { enrollment_id: 'e2', points: '0', note: '' }, { enrollment_id: 'e3', points: null, note: '' }];
    await api.scores.saveRecords('c1', 'i1', { expected_version: 4, records });
    expect(fetcher).toHaveBeenCalledWith('/api/v1/classes/c1/scores/items/i1/records', expect.objectContaining({ method: 'PUT', body: JSON.stringify({ expected_version: 4, records }) }));
    await api.scores.saveSettings('c1', { expected_version: 5, base_score: '80', factors: { HOMEWORK: '0.5', LAB: '1', CLASSROOM: '1', OTHER: null } });
    expect(fetcher).toHaveBeenLastCalledWith('/api/v1/classes/c1/scores/settings', expect.objectContaining({ method: 'PUT' }));
    await api.scores.history('c1', 'e1');
    expect(fetcher).toHaveBeenLastCalledWith('/api/v1/classes/c1/scores/history?enrollment_id=e1', expect.anything());
    await api.scores.export('c1', 'xlsx', 'details');
    expect(fetcher).toHaveBeenLastCalledWith('/api/v1/classes/c1/scores/export?format=xlsx&kind=details', expect.anything());
  });
});
