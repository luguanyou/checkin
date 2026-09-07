import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AttendancePage } from './AttendancePage';

const records = [
  { id: 'r1', student_id: 's1', student_number: '20260001', student_name: '张敏', class_name: '一班', status: 'pending', marked_at: null, last_modified_at: null, last_modified_by: { id: 'u1', display_name: '教师' }, version: 1 },
  { id: 'r2', student_id: 's2', student_number: '20260002', student_name: '李明', class_name: '一班', status: 'pending', marked_at: null, last_modified_at: null, last_modified_by: { id: 'u1', display_name: '教师' }, version: 1 },
];
const api = { attendance: { get: vi.fn(), updateRecord: vi.fn(), complete: vi.fn() } };
vi.mock('../../app/auth', () => ({ useApi: () => api }));

const speak = vi.fn();
vi.mock('../../hooks/useSpeech', () => ({
  useSpeech: () => ({ muted: false, supported: true, speak, toggleMuted: vi.fn(), rate: 0.9, voices: [], voiceName: '', setRate: vi.fn(), setVoice: vi.fn() }),
}));

describe('AttendancePage', () => {
  it('marks the current student from the keyboard and advances', async () => {
    api.attendance.get.mockResolvedValue({ id: 'session-1', status: 'DRAFT', course: { id: 'c', name: '产品设计', code: 'PD' }, class_group: { id: 'g', name: '一班' }, session_date: '2026-09-03', summary: { total: 2, pending: 2, present: 0, absent: 0, leave: 0, late: 0, exceptions: 0 }, records, started_at: '', completed_at: null, created_at: '', updated_at: '' });
    api.attendance.updateRecord.mockImplementation(async (_id: string, input: { status: string }) => ({ ...records[0], status: input.status, version: 2 }));
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/attendance/session-1']}><Routes><Route path="/attendance/:sessionId" element={<AttendancePage />} /></Routes></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole('heading', { name: '张敏' })).toBeInTheDocument();
    await userEvent.keyboard('1');
    expect(await screen.findByRole('heading', { name: '李明' })).toBeInTheDocument();
    await waitFor(() => expect(api.attendance.updateRecord).toHaveBeenCalledWith('r1', expect.objectContaining({ status: 'absent', expected_version: 1 })));
    expect(speak).toHaveBeenCalledTimes(1);
    expect(speak).toHaveBeenCalledWith('鏉庢槑');
  });
});
