import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { StudentPortalPage } from './StudentPortalPage';
import { StudentAccountDialog, StudentPasswordResetDialog, StudentVisibilityDialog } from './TeacherPortalDialogs';
import { ToastProvider } from '../../components/ToastProvider';

const portal = { classes: vi.fn(), get: vi.fn(), visibility: vi.fn(), setVisibility: vi.fn(), resetPassword: vi.fn(), createAccount: vi.fn() };
const teachingContent = { studentList: vi.fn() };
vi.mock('../../app/auth', () => ({ useApi: () => ({ portal, teachingContent }), useAuth: () => ({ user: { id: 'u1', display_name: '小明', username: '001' }, logout: vi.fn() }) }));
function mount(children: React.ReactNode, path = '/student') {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><ToastProvider>{children}</ToastProvider></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks();
  portal.classes.mockResolvedValue({ items: [{ id: 'c1', name: '一班', course_name: '设计', term: '2026', attendance_visible: false, score_visibility: 'HIDDEN' }] });
  portal.get.mockResolvedValue({ attendance_visible: false, score_visibility: 'HIDDEN', attendance: null, score: null, details: null });
  teachingContent.studentList.mockResolvedValue({ items: [] });
});
it('explains closed visibility without showing grades or attendance', async () => {
  mount(<StudentPortalPage />, '/student?class=c1');
  expect(await screen.findByText('老师暂未开放考勤查看')).toBeInTheDocument();
  expect(screen.getByText('老师暂未开放平时分查看')).toBeInTheDocument();
  expect(screen.queryByText('项目明细')).not.toBeInTheDocument();
});
it('shows only the total in total-only mode', async () => {
  portal.get.mockResolvedValue({ attendance_visible: false, score_visibility: 'TOTAL', attendance: null, score: { final_score: '75.25', status: 'READY' }, details: null });
  mount(<StudentPortalPage />, '/student?class=c1');
  expect(await screen.findByText('75.3')).toBeInTheDocument();
  expect(screen.queryByText('项目明细')).not.toBeInTheDocument();
  expect(screen.queryByText('评分规则')).not.toBeInTheDocument();
});
it('waits for an explicit choice between same-named classes and only loads the selected course', async () => {
  const user = userEvent.setup();
  const course = { name: '一班', course_name: '设计', term: '2026', attendance_visible: false, score_visibility: 'HIDDEN' };
  portal.classes.mockResolvedValue({ items: [
    { ...course, id: 'c1', teacher_name: '张老师' },
    { ...course, id: 'c2', teacher_name: '李老师' },
  ] });
  mount(<StudentPortalPage />);
  const select = await screen.findByLabelText('课程班级');
  expect(select).toHaveValue('');
  expect(portal.get).not.toHaveBeenCalled();
  expect(teachingContent.studentList).not.toHaveBeenCalled();
  await user.selectOptions(select, '设计 · 一班 · 2026 · 李老师');
  await waitFor(() => expect(portal.get).toHaveBeenCalledExactlyOnceWith('c2'));
  await waitFor(() => expect(teachingContent.studentList).toHaveBeenCalledExactlyOnceWith('c2'));
});
it('lets teachers set attendance and score visibility independently', async () => {
  const user = userEvent.setup(); const close = vi.fn();
  portal.visibility.mockResolvedValue({ attendance_visible: false, score_visibility: 'HIDDEN' });
  portal.setVisibility.mockResolvedValue({ attendance_visible: true, score_visibility: 'TOTAL' });
  mount(<StudentVisibilityDialog classId="c1" onClose={close} />);
  await user.selectOptions(await screen.findByLabelText('考勤数据'), 'true');
  await user.selectOptions(screen.getByLabelText('平时分数据'), 'TOTAL');
  await user.click(screen.getByRole('button', { name: '保存设置' }));
  await waitFor(() => expect(portal.setVisibility).toHaveBeenCalledWith('c1', { attendance_visible: true, score_visibility: 'TOTAL' }));
  await waitFor(() => expect(close).toHaveBeenCalled());
});
it('keeps the selected settings after a failed save', async () => {
  const user = userEvent.setup(); const close = vi.fn();
  portal.visibility.mockResolvedValue({ attendance_visible: false, score_visibility: 'HIDDEN' });
  portal.setVisibility.mockRejectedValue(new Error('保存失败'));
  mount(<StudentVisibilityDialog classId="c1" onClose={close} />);
  await user.selectOptions(await screen.findByLabelText('平时分数据'), 'DETAILS');
  await user.click(screen.getByRole('button', { name: '保存设置' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('保存失败');
  expect(screen.getByLabelText('平时分数据')).toHaveValue('DETAILS');
  expect(close).not.toHaveBeenCalled();
});

it('confirms the student password reset and shows the returned login credentials', async () => {
  const user = userEvent.setup();
  portal.resetPassword.mockResolvedValue({ username: '001' });
  mount(<StudentPasswordResetDialog classId="c1" student={{ id: 's1', student_number: '001', name: '小明', gender: null, major: null }} onClose={vi.fn()} />);
  expect(screen.queryByLabelText('临时密码')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '确认重置' }));
  const password = await screen.findByLabelText('临时密码');
  expect(portal.resetPassword).toHaveBeenCalledWith('c1', 's1', (password as HTMLInputElement).value);
  expect((password as HTMLInputElement).value).toMatch(/^[0-9]{8}$/);
  expect(screen.getByText('001', { exact: true })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '确认重置' })).not.toBeInTheDocument();
});

it('keeps the reset dialog open and hides credentials when the teacher lacks access', async () => {
  const user = userEvent.setup();
  portal.resetPassword.mockRejectedValue(new Error('学生不在当前班级中'));
  mount(<StudentPasswordResetDialog classId="c1" student={{ id: 's1', student_number: '001', name: '小明', gender: null, major: null }} onClose={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: '确认重置' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('学生不在当前班级中');
  expect(screen.queryByLabelText('临时密码')).not.toBeInTheDocument();
});

it('creates a student account with eight random digits and displays the credential after success', async () => {
  const user = userEvent.setup();
  portal.createAccount.mockResolvedValue({ username: '001' });
  mount(<StudentAccountDialog classId="c1" student={{ id: 's1', student_number: '001', name: '小明', gender: null, major: null }} onClose={vi.fn()} />);
  expect(screen.queryByLabelText('临时密码')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '确认开通' }));
  const password = await screen.findByLabelText('临时密码') as HTMLInputElement;
  expect(password.value).toMatch(/^[0-9]{8}$/);
  expect(portal.createAccount).toHaveBeenCalledWith('c1', 's1', password.value);
});
