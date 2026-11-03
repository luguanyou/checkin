import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { MonitorPage } from './MonitorPage';
import { MonitorManagementDialog } from './MonitorManagementDialog';
import { ToastProvider } from '../../components/ToastProvider';
import { ApiError } from '../../api/client';

const monitors = { manage: vi.fn(), setGrants: vi.fn(), projects: vi.fn(), get: vi.fn(), save: vi.fn() };
vi.mock('../../app/auth', () => ({ useApi: () => ({ monitors }) }));
const item = { id: 'i1', name: '作业一', category: 'HOMEWORK', occurred_on: '2026-11-02', description: '', default_points: null };
const project = { version: 2, item, students: [
  { enrollment_id: 'e1', student_id: 's1', student_number: '001', student_name: '班长', enrollment_status: 'ACTIVE', can_edit: false },
  { enrollment_id: 'e2', student_id: 's2', student_number: '002', student_name: '同学', enrollment_status: 'ACTIVE', can_edit: true },
], records: [] };
const management = { readonly: false, items: [item], members: [{ student: { id: 's1', student_number: '001', name: '班长' }, enrollment_status: 'ACTIVE', user_id: 'u1', username: '001', account_status: 'ACTIVE', item_ids: ['i1'] }] };
function mount(children: React.ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/student/monitor/c1']}><ToastProvider>{children}</ToastProvider></MemoryRouter></QueryClientProvider>); }
function mountPage() { mount(<Routes><Route path="/student/monitor/:classId" element={<MonitorPage />} /></Routes>); }
beforeEach(() => {
  vi.clearAllMocks(); monitors.projects.mockResolvedValue({ items: [{ ...item, class_id: 'c1' }] }); monitors.get.mockResolvedValue(project); monitors.save.mockResolvedValue({ ...project, version: 3 }); monitors.manage.mockResolvedValue(management); monitors.setGrants.mockResolvedValue(management);
});
it('only offers authorized projects and saves edits while keeping own score read-only', async () => {
  const user = userEvent.setup(); mountPage();
  expect(await screen.findByLabelText('班长本次积分')).toBeDisabled();
  expect(screen.queryByRole('button', { name: '新建项目' })).not.toBeInTheDocument();
  expect(screen.getAllByRole('option')).toHaveLength(1);
  await user.clear(screen.getByLabelText('同学本次积分'));
  await user.type(screen.getByLabelText('同学本次积分'), '2.5');
  await user.type(screen.getByLabelText('同学备注'), '课堂登记');
  await user.click(screen.getByRole('button', { name: '保存本次录入' }));
  await waitFor(() => expect(monitors.save).toHaveBeenCalledWith('c1', 'i1', { expected_version: 2, records: [{ enrollment_id: 'e2', points: '2.5', note: '课堂登记' }] }));
});
it('preserves input and blocks stale retries on a version conflict', async () => {
  const user = userEvent.setup(); monitors.save.mockRejectedValue(new ApiError(409, 'SCORE_VERSION_CONFLICT', '版本冲突')); mountPage();
  await user.clear(await screen.findByLabelText('同学本次积分')); await user.type(screen.getByLabelText('同学本次积分'), '3');
  await user.click(screen.getByRole('button', { name: '保存本次录入' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('版本冲突');
  expect(screen.getByLabelText('同学本次积分')).toHaveValue(3);
  expect(screen.getByRole('button', { name: '保存本次录入' })).toBeDisabled();
});
it('lets the teacher revoke every project for a monitor', async () => {
  const user = userEvent.setup(); mount(<MonitorManagementDialog classId="c1" onClose={vi.fn()} />);
  expect(await screen.findByRole('checkbox', { name: /作业一/ })).toBeChecked();
  await user.click(screen.getByRole('button', { name: '撤销全部授权' }));
  await waitFor(() => expect(monitors.setGrants).toHaveBeenCalledWith('c1', 'u1', []));
});
it('preserves the selected grants on a save failure', async () => {
  const user = userEvent.setup(); monitors.setGrants.mockRejectedValue(new Error('授权失败')); mount(<MonitorManagementDialog classId="c1" onClose={vi.fn()} />);
  await user.click(await screen.findByRole('checkbox', { name: /作业一/ }));
  await user.click(screen.getByRole('button', { name: '保存授权' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('授权失败');
  expect(screen.getByRole('checkbox', { name: /作业一/ })).not.toBeChecked();
});
it('requires an account before the teacher can grant projects', async () => {
  monitors.manage.mockResolvedValue({ ...management, members: [{ ...management.members[0], user_id: null, username: null, account_status: null, item_ids: [] }] });
  mount(<MonitorManagementDialog classId="c1" onClose={vi.fn()} />);
  expect(await screen.findByText('该学生尚未开通账号，请先开通再授权。')).toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: /作业一/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: '保存授权' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '开通学生账号' })).toBeEnabled();
});
it('allows reviewer-only authorization without granting a scoring project', async () => {
  const user = userEvent.setup();
  monitors.manage.mockResolvedValue({ ...management, members: [{ ...management.members[0], item_ids: [] }] });
  mount(<MonitorManagementDialog classId="c1" onClose={vi.fn()} />);
  await user.click(await screen.findByRole('checkbox', { name: '允许审核本班学生注册' }));
  await user.click(screen.getByRole('button', { name: '保存授权' }));
  await waitFor(() => expect(monitors.setGrants).toHaveBeenCalledWith('c1', 'u1', [], true));
});
