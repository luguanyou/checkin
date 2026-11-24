import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../components/ToastProvider';
import { RecordsPage } from './RecordsPage';
import { RecordDetailPage } from './RecordDetailPage';

const session = { id: 'session-1', status: 'COMPLETED', course: { id: 'c', name: '产品设计', code: 'PD' }, class_group: { id: 'g', name: '一班' }, session_date: '2026-09-03', summary: { total: 1, pending: 0, present: 0, absent: 1, leave: 0, late: 0, exceptions: 1 }, records: [{ id: 'r1', student_id: 's1', student_number: '20260001', student_name: '张敏', class_name: '一班', status: 'absent', marked_at: '', last_modified_at: '', last_modified_by: { id: 'u', display_name: '教师' }, version: 2 }], started_at: '', completed_at: '', created_at: '', updated_at: '' };
const api = { attendance: { list: vi.fn(), get: vi.fn(), updateRecord: vi.fn(), export: vi.fn(), exportCourse: vi.fn(), exportTemplate: vi.fn(), exportScores: vi.fn() }, courses: { list: vi.fn() } };
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
  it('exports the entire selected course independently of list date and status filters', async () => {
    const user = userEvent.setup();
    api.courses.list.mockResolvedValue({ items: [{ id: 'c', name: '产品设计', classes: [{ id: 'g', name: '一班' }] }] });
    api.attendance.exportCourse.mockResolvedValue({ blob: new Blob(['xlsx']), filename: '课程考勤.xlsx' });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    URL.createObjectURL = vi.fn(() => 'blob:export');
    URL.revokeObjectURL = vi.fn();
    render(wrap(<RecordsPage />, '/records?course_id=c&class_group_id=g&date_from=2026-09-01&status=DRAFT'));
    await user.click(await screen.findByRole('button', { name: '导出课程考勤' }));
    expect(screen.getByText(/不受列表日期、状态和分页影响/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '生成 Excel' }));
    expect(api.attendance.exportCourse).toHaveBeenCalledWith('c', 'g');
    expect(await screen.findByText('课程考勤汇总已生成')).toBeInTheDocument();
    expect(click).toHaveBeenCalled();
    click.mockRestore();
  });
  it('requires a selected course for course export', async () => {
    render(wrap(<RecordsPage />, '/records'));
    expect(await screen.findByRole('button', { name: '导出课程考勤' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '按模板导出（含平时分）' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '导出平时分' })).toBeDisabled();
  });
  it('downloads the original template with scores through a separate button', async () => {
    const user = userEvent.setup();
    api.attendance.exportTemplate.mockResolvedValue({ blob: new Blob(['xlsx']), filename: '模板.xlsx' });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    URL.createObjectURL = vi.fn(() => 'blob:template'); URL.revokeObjectURL = vi.fn();
    render(wrap(<RecordsPage />, '/records?course_id=c'));
    await user.click(await screen.findByRole('button', { name: '按模板导出（含平时分）' }));
    expect(screen.getByText(/平时分沿用/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '生成 Excel' }));
    expect(api.attendance.exportTemplate).toHaveBeenCalledWith('c', undefined);
    expect(await screen.findByText('模板考勤与平时成绩已生成')).toBeInTheDocument();
    expect(click).toHaveBeenCalled();
  });
  it('downloads scores only for the selected course and class', async () => {
    const user = userEvent.setup();
    api.attendance.exportScores.mockResolvedValue({ blob: new Blob(['xlsx']), filename: '平时分.xlsx' });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    URL.createObjectURL = vi.fn(() => 'blob:scores'); URL.revokeObjectURL = vi.fn();
    render(wrap(<RecordsPage />, '/records?course_id=c&class_group_id=g'));
    await user.click(await screen.findByRole('button', { name: '导出平时分' }));
    expect(screen.getByText(/导出每位学生的百分制平时分/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '生成 Excel' }));
    expect(api.attendance.exportScores).toHaveBeenCalledWith('c', 'g');
    expect(await screen.findByText('平时分已生成')).toBeInTheDocument();
  });
});
