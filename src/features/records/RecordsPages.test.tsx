import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../components/ToastProvider';
import { RecordsPage } from './RecordsPage';
import { RecordDetailPage } from './RecordDetailPage';

const session = { id: 'session-1', status: 'COMPLETED', course: { id: 'c', name: '产品设计', code: 'PD' }, class_group: { id: 'g', name: '一班' }, session_date: '2026-09-03', summary: { total: 1, pending: 0, present: 0, absent: 1, leave: 0, late: 0, exceptions: 1 }, records: [{ id: 'r1', student_id: 's1', student_number: '20260001', student_name: '张敏', class_name: '一班', status: 'absent', marked_at: '', last_modified_at: '', last_modified_by: { id: 'u', display_name: '教师' }, version: 2 }], started_at: '', completed_at: '', created_at: '', updated_at: '' };
const api = { attendance: { list: vi.fn(), get: vi.fn(), updateRecord: vi.fn(), export: vi.fn() }, courses: { list: vi.fn() } };
vi.mock('../../app/auth', () => ({ useApi: () => api }));
const wrap = (node: React.ReactNode, path: string) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><ToastProvider>{node}</ToastProvider></MemoryRouter></QueryClientProvider>;

describe('record pages', () => {
  beforeEach(() => {
    api.attendance.list.mockResolvedValue({ items: [session], page: 1, page_size: 20, total: 1 });
    api.attendance.get.mockResolvedValue(session);
    api.courses.list.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
  });
  it('renders sessions returned by the API', async () => {
    render(wrap(<RecordsPage />, '/records'));
    expect(await screen.findByText('产品设计')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看详情' })).toHaveAttribute('href', '/records/session-1');
  });
  it('renders record details and a correction action', async () => {
    render(wrap(<Routes><Route path="/records/:sessionId" element={<RecordDetailPage />} /></Routes>, '/records/session-1'));
    expect(await screen.findByText('张敏')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '修正' })).toBeInTheDocument();
  });
});
