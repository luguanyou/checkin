import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DashboardPage } from './dashboard/DashboardPage';
import { CoursesPage } from './courses/CoursesPage';
import { RosterPage } from './roster/RosterPage';
import { ToastProvider } from '../components/ToastProvider';

const api = {
  courses: { list: vi.fn(), update: vi.fn(), updateClass: vi.fn(), delete: vi.fn(), deleteClass: vi.fn() },
  attendance: { list: vi.fn() },
  roster: { list: vi.fn() },
};
vi.mock('../app/auth', () => ({ useApi: () => api }));

const course = {
  id: 'course-1', name: '产品设计方法', code: 'PD204', term: '2026 秋季学期', status: 'ACTIVE',
  classes: [{ id: 'class-1', name: '2024 级 2 班', status: 'ACTIVE', active_student_count: 48 }],
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
};
const page = { items: [course], page: 1, page_size: 20, total: 1 };

function wrapper(children: React.ReactNode, path = '/') {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><ToastProvider>{children}</ToastProvider></MemoryRouter></QueryClientProvider>;
}

describe('business pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.courses.list.mockResolvedValue(page);
    api.attendance.list.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
    api.roster.list.mockResolvedValue({ items: [{ enrollment_id: 'e1', enrollment_status: 'ACTIVE', student: { id: 's1', student_number: '20260001', name: '张敏', gender: '女', major: '工业设计' }, created_at: '', updated_at: '' }], page: 1, page_size: 20, total: 1 });
  });

  it('renders dashboard metrics derived from API data', async () => {
    render(wrapper(<DashboardPage />));
    expect(await screen.findByText('1 门')).toBeInTheDocument();
    expect(screen.getByText('1 个')).toBeInTheDocument();
  });

  it('renders courses and their classes', async () => {
    render(wrapper(<CoursesPage />));
    expect(await screen.findByText('产品设计方法')).toBeInTheDocument();
    expect(screen.getByText('2024 级 2 班')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '管理名单' })).toHaveAttribute('href', '/classes/class-1/roster');
  });

  it('restores an archived course', async () => {
    const user = userEvent.setup();
    api.courses.list.mockResolvedValue({ ...page, items: [{ ...course, status: 'ARCHIVED' }] });
    api.courses.update.mockResolvedValue({ ...course, status: 'ACTIVE' });
    render(wrapper(<CoursesPage />, '/courses?status=ARCHIVED'));

    await user.click(await screen.findByRole('button', { name: '恢复课程' }));

    await waitFor(() => expect(api.courses.update).toHaveBeenCalledWith('course-1', { status: 'ACTIVE' }));
  });

  it('edits course and class names', async () => {
    const user = userEvent.setup();
    api.courses.update.mockResolvedValue({ ...course, name: '新课程名' });
    api.courses.updateClass.mockResolvedValue({ ...course.classes[0], name: '新班级名' });
    render(wrapper(<CoursesPage />));

    await user.click(await screen.findByRole('button', { name: '编辑课程' }));
    const courseName = screen.getByLabelText('课程名称');
    await user.clear(courseName);
    await user.type(courseName, '新课程名');
    await user.click(screen.getByRole('button', { name: '保存课程' }));
    expect(api.courses.update).toHaveBeenCalledWith('course-1', { name: '新课程名' });

    await user.click(screen.getByRole('button', { name: '编辑班级 2024 级 2 班' }));
    const className = screen.getByLabelText('班级名称');
    await user.clear(className);
    await user.type(className, '新班级名');
    await user.click(screen.getByRole('button', { name: '保存班级' }));
    expect(api.courses.updateClass).toHaveBeenCalledWith('class-1', { name: '新班级名' });
  });

  it('deletes a course and class after confirmation', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.courses.delete.mockResolvedValue(undefined);
    api.courses.deleteClass.mockResolvedValue(undefined);
    render(wrapper(<CoursesPage />));

    await user.click(await screen.findByRole('button', { name: '删除班级 2024 级 2 班' }));
    await waitFor(() => expect(api.courses.deleteClass).toHaveBeenCalledWith('class-1', true));
    await user.click(screen.getByRole('button', { name: '删除课程' }));
    await waitFor(() => expect(api.courses.delete).toHaveBeenCalledWith('course-1'));
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/学生名单.*历史考勤记录.*永久删除.*无法恢复/));
    confirm.mockRestore();
  });

  it('deletes the current class from its roster page', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.courses.deleteClass.mockResolvedValue(undefined);
    render(wrapper(<Routes><Route path="/classes/:classId/roster" element={<RosterPage />} /><Route path="/courses" element={<div>课程班级页</div>} /></Routes>, '/classes/class-1/roster'));

    await user.click(await screen.findByRole('button', { name: '删除班级' }));

    await waitFor(() => expect(api.courses.deleteClass).toHaveBeenCalledWith('class-1', true));
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/学生名单.*历史考勤记录.*永久删除.*无法恢复/));
    expect(await screen.findByText('课程班级页')).toBeInTheDocument();
    confirm.mockRestore();
  });

  it('loads the roster selected by the route', async () => {
    render(wrapper(<Routes><Route path="/classes/:classId/roster" element={<RosterPage />} /></Routes>, '/classes/class-1/roster'));
    expect(await screen.findByText('张敏')).toBeInTheDocument();
    expect(api.roster.list).toHaveBeenCalledWith('class-1', expect.objectContaining({ page: 1 }));
  });
});

it('adds a student through the roster dialog and keeps errors editable', async () => {
  const user = userEvent.setup();
  const create = vi.fn().mockRejectedValueOnce(new Error('该学生已在当前班级名单中')).mockResolvedValue({});
  Object.assign(api.roster, { create });
  api.courses.list.mockResolvedValue(page);
  api.roster.list.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
  render(wrapper(<Routes><Route path="/classes/:classId/roster" element={<RosterPage />} /></Routes>, '/classes/class-1/roster'));
  await user.click(await screen.findByRole('button', { name: '新增学生' }));
  await user.type(screen.getByLabelText('学号'), '0099');
  await user.type(screen.getByLabelText('姓名'), '新同学');
  await user.click(screen.getByRole('button', { name: '保存' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('该学生已在当前班级名单中');
  expect(screen.getByLabelText('学号')).toHaveValue('0099');
  await user.click(screen.getByRole('button', { name: '保存' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(create).toHaveBeenCalledWith('class-1', { student_number: '0099', name: '新同学', gender: undefined, major: undefined });
});

it('edits an existing roster member and keeps values after a failed save', async () => {
  const user = userEvent.setup();
  const member = { enrollment_id: 'e1', enrollment_status: 'ACTIVE', student: { id: 's1', student_number: '001', name: '原姓名', gender: '女', major: '原专业' } };
  const update = vi.fn().mockRejectedValueOnce(new Error('该学号已存在')).mockResolvedValue({ ...member, student: { ...member.student, name: '新姓名', major: null } });
  Object.assign(api.roster, { update });
  api.courses.list.mockResolvedValue(page);
  api.roster.list.mockResolvedValue({ items: [member], page: 1, page_size: 20, total: 1 });
  render(wrapper(<Routes><Route path="/classes/:classId/roster" element={<RosterPage />} /></Routes>, '/classes/class-1/roster'));
  await user.click(await screen.findByRole('button', { name: '编辑原姓名' }));
  expect(screen.getByLabelText('学号')).toHaveValue('001');
  expect(screen.getByLabelText('姓名')).toHaveValue('原姓名');
  await user.clear(screen.getByLabelText('姓名')); await user.type(screen.getByLabelText('姓名'), '新姓名');
  await user.clear(screen.getByLabelText('专业'));
  await user.click(screen.getByRole('button', { name: '保存' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('该学号已存在');
  expect(screen.getByLabelText('姓名')).toHaveValue('新姓名');
  await user.click(screen.getByRole('button', { name: '保存' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(update).toHaveBeenCalledWith('class-1', 'e1', { student_number: '001', name: '新姓名', gender: '女', major: undefined });
});
