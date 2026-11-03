import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { StudentRegistrationPage } from './StudentRegistrationPage';
import { RegistrationReviewPage } from './RegistrationReviewPage';
import { ToastProvider } from '../../components/ToastProvider';
const registrations = { lookup: vi.fn(), register: vi.fn(), list: vi.fn(), review: vi.fn() };
vi.mock('../../app/auth', () => ({ useApi: () => ({ registrations }), useAuth: () => ({ user: { role: 'TEACHER' } }) }));
function mount(element: React.ReactNode, review = false, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[review ? '/classes/c1/registrations' : '/register']}><ToastProvider><Routes><Route path={review ? '/classes/:classId/registrations' : '/register'} element={element} /></Routes></ToastProvider></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks(); registrations.lookup.mockResolvedValue({ items: [{ id: 'c1', name: '一班', course_name: '设计', term: '2026' }] }); registrations.register.mockResolvedValue({ status: 'PENDING' });
  registrations.list.mockResolvedValue({ items: [
    { id: 'r1', name: '同学', student_number: '001', status: 'PENDING', created_at: '2026-11-03T00:00:00', can_review: true },
    { id: 'self', name: '自己', student_number: '002', status: 'PENDING', created_at: '2026-11-03T00:00:00', can_review: false },
  ] }); registrations.review.mockResolvedValue({ reviewed: 1 });
});
it('matches roster then submits a self-chosen password without logging in', async () => {
  const user = userEvent.setup(); mount(<StudentRegistrationPage />);
  await user.type(screen.getByLabelText('学号'), '001'); await user.type(screen.getByLabelText('姓名'), '同学');
  await user.click(screen.getByRole('button', { name: '匹配班级名单' }));
  await user.type(await screen.findByLabelText('设置密码'), 'Student-password-123'); await user.type(screen.getByLabelText('确认密码'), 'Student-password-123');
  await user.click(screen.getByRole('button', { name: '提交注册申请' }));
  expect(await screen.findByText(/申请已提交，等待任课老师/)).toBeInTheDocument();
  expect(registrations.register).toHaveBeenCalledWith({ student_number: '001', name: '同学', class_id: 'c1', password: 'Student-password-123' });
  expect(screen.queryByLabelText('设置密码')).not.toBeInTheDocument();
});
it('keeps form values when a duplicate pending application is rejected', async () => {
  const user = userEvent.setup(); registrations.register.mockRejectedValue(new Error('申请已提交，请等待审核')); mount(<StudentRegistrationPage />);
  await user.type(screen.getByLabelText('学号'), '001'); await user.type(screen.getByLabelText('姓名'), '同学'); await user.click(screen.getByRole('button', { name: '匹配班级名单' }));
  await user.type(await screen.findByLabelText('设置密码'), 'Student-password-123'); await user.type(screen.getByLabelText('确认密码'), 'Student-password-123');
  await user.click(screen.getByRole('button', { name: '提交注册申请' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('请等待审核'); expect(screen.getByLabelText('学号')).toHaveValue('001');
});
it('batch approval excludes requests that cannot be self-reviewed', async () => {
  const user = userEvent.setup(); mount(<RegistrationReviewPage />, true);
  expect(await screen.findByRole('checkbox', { name: '选择自己的申请' })).toBeDisabled();
  await user.click(screen.getByRole('checkbox', { name: '全选待审核申请' }));
  await user.click(screen.getByRole('button', { name: '通过所选（1）' }));
  await waitFor(() => expect(registrations.review).toHaveBeenCalledWith('c1', ['r1'], 'APPROVED', undefined));
});
it('retains selection and reason when review fails', async () => {
  const user = userEvent.setup(); registrations.review.mockRejectedValue(new Error('授权已撤销')); mount(<RegistrationReviewPage />, true);
  await user.click(await screen.findByRole('checkbox', { name: '选择同学的申请' }));
  await user.type(screen.getByLabelText('审核备注（选填，驳回时向学生说明原因）'), '请核对身份');
  await user.click(screen.getByRole('button', { name: '驳回所选' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('授权已撤销'); expect(screen.getByRole('checkbox', { name: '选择同学的申请' })).toBeChecked();
});

it('reloads a recently cached empty list when the teacher returns after registration', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } });
  client.setQueryData(['registrations', 'c1', 'PENDING'], { items: [] });
  mount(<RegistrationReviewPage />, true, client);
  expect(await screen.findByText('同学')).toBeInTheDocument();
  expect(registrations.list).toHaveBeenCalledWith('c1', 'PENDING');
});

it('automatically fetches new applications while the review page stays open', async () => {
  registrations.list.mockResolvedValueOnce({ items: [] });
  vi.useFakeTimers();
  try {
    mount(<RegistrationReviewPage />, true);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.getByText('暂无匹配的注册申请')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(15_001); });
    expect(registrations.list).toHaveBeenCalledTimes(2);
    expect(screen.getByText('同学')).toBeInTheDocument();
  } finally { vi.useRealTimers(); }
});
