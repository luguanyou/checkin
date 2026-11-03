import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { StudentPortalPage } from './StudentPortalPage';
import { StudentVisibilityDialog } from './TeacherPortalDialogs';
import { ToastProvider } from '../../components/ToastProvider';

const portal = { classes: vi.fn(), get: vi.fn(), visibility: vi.fn(), setVisibility: vi.fn() };
vi.mock('../../app/auth', () => ({ useApi: () => ({ portal }), useAuth: () => ({ user: { id: 'u1', display_name: '小明', username: '001' }, logout: vi.fn() }) }));
function mount(children: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ToastProvider>{children}</ToastProvider></QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks();
  portal.classes.mockResolvedValue({ items: [{ id: 'c1', name: '一班', course_name: '设计', term: '2026', attendance_visible: false, score_visibility: 'HIDDEN' }] });
  portal.get.mockResolvedValue({ attendance_visible: false, score_visibility: 'HIDDEN', attendance: null, score: null, details: null });
});
it('explains closed visibility without showing grades or attendance', async () => {
  mount(<StudentPortalPage />);
  expect(await screen.findByText('老师暂未开放考勤查看')).toBeInTheDocument();
  expect(screen.getByText('老师暂未开放平时分查看')).toBeInTheDocument();
  expect(screen.queryByText('项目明细')).not.toBeInTheDocument();
});
it('shows only the total in total-only mode', async () => {
  portal.get.mockResolvedValue({ attendance_visible: false, score_visibility: 'TOTAL', attendance: null, score: { final_score: '75.25', status: 'READY' }, details: null });
  mount(<StudentPortalPage />);
  expect(await screen.findByText('75.3')).toBeInTheDocument();
  expect(screen.queryByText('项目明细')).not.toBeInTheDocument();
  expect(screen.queryByText('评分规则')).not.toBeInTheDocument();
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
