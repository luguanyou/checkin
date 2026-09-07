import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../components/ToastProvider';
import { AdminPage } from './AdminPage';

const teacher = {
  id: 'teacher-1',
  username: 'wang01',
  display_name: '王老师',
  role: 'TEACHER' as const,
  status: 'ACTIVE' as const,
  must_change_password: true,
  last_login_at: null,
  created_at: '2026-09-04T00:00:00Z',
  updated_at: '2026-09-04T00:00:00Z',
};

const logout = vi.fn();
const api = {
  adminUsers: {
    list: vi.fn(),
    create: vi.fn(),
    updateStatus: vi.fn(),
    resetPassword: vi.fn(),
  },
};

vi.mock('../../app/auth', () => ({
  useApi: () => api,
  useAuth: () => ({
    user: { display_name: '超级管理员', username: 'admin' },
    logout,
  }),
}));

vi.mock('./temporary-password', () => ({
  generateTemporaryPassword: () => 'Abcd2345Efgh6789',
}));

function userPage(items = [teacher], total = items.length, pageSize = 20) {
  return { items, page: 1, page_size: pageSize, total };
}

function renderPage(path = '/admin') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider><AdminPage /></ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.adminUsers.list.mockImplementation(({ page_size: pageSize, status, q }) => {
      if (pageSize === 1) {
        return Promise.resolve(userPage([], status === 'DISABLED' ? 2 : status === 'ACTIVE' ? 8 : 10, 1));
      }
      return Promise.resolve(userPage(q === 'missing' ? [] : [teacher], q === 'missing' ? 0 : 1));
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads only teacher accounts and renders independent account counts', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: '教师账号' })).toBeInTheDocument();
    await screen.findAllByText('王老师');
    expect(screen.getAllByText('王老师')).not.toHaveLength(0);
    expect(screen.getAllByText('首次登录需改密')).not.toHaveLength(0);
    await waitFor(() => {
      expect(screen.getByLabelText('教师账号总数')).toHaveTextContent('10');
      expect(screen.getByLabelText('启用教师数')).toHaveTextContent('8');
      expect(screen.getByLabelText('停用教师数')).toHaveTextContent('2');
    });
    expect(api.adminUsers.list).toHaveBeenCalledWith(expect.objectContaining({
      role: 'TEACHER', page: 1, page_size: 20,
    }));
  });

  it('maps URL search and status controls to list parameters', async () => {
    renderPage('/admin?q=wang&status=DISABLED&page=2');

    await screen.findByRole('heading', { name: '教师账号' });
    expect(screen.getByLabelText('搜索教师')).toHaveValue('wang');
    expect(screen.getByLabelText('账号状态')).toHaveValue('DISABLED');
    expect(api.adminUsers.list).toHaveBeenCalledWith(expect.objectContaining({
      role: 'TEACHER', q: 'wang', status: 'DISABLED', page: 2, page_size: 20,
    }));

    await userEvent.clear(screen.getByLabelText('搜索教师'));
    await userEvent.type(screen.getByLabelText('搜索教师'), 'missing');

    await waitFor(() => expect(api.adminUsers.list).toHaveBeenCalledWith(expect.objectContaining({
      q: 'missing', status: 'DISABLED', page: 1,
    })));
    expect(await screen.findByRole('heading', { name: '没有匹配的教师账号' })).toBeInTheDocument();
  });

  it('creates a teacher and shows copyable credentials only until completion', async () => {
    api.adminUsers.create.mockResolvedValue({ ...teacher, id: 'teacher-2', username: 'li02', display_name: '李老师' });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    renderPage();

    await screen.findByRole('heading', { name: '教师账号' });
    await userEvent.click(screen.getByRole('button', { name: '创建教师' }));
    await userEvent.type(screen.getByLabelText('教师姓名'), ' 李老师 ');
    await userEvent.type(screen.getByLabelText('用户名'), ' Li02 ');
    await userEvent.click(screen.getByRole('button', { name: '确认创建' }));

    expect(api.adminUsers.create).toHaveBeenCalledWith({
      display_name: '李老师',
      username: 'li02',
      temporary_password: 'Abcd2345Efgh6789',
    });
    expect(await screen.findByRole('heading', { name: '一次性登录凭据' })).toBeInTheDocument();
    expect(screen.getByText('Abcd2345Efgh6789')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '复制登录凭据' }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('Abcd2345Efgh6789'));
    await userEvent.click(screen.getByRole('button', { name: '完成' }));
    expect(screen.queryByText('Abcd2345Efgh6789')).not.toBeInTheDocument();
  });

  it('keeps create form values when the API rejects the username', async () => {
    api.adminUsers.create.mockRejectedValue(new Error('用户名已存在'));
    renderPage();

    await screen.findByRole('heading', { name: '教师账号' });
    await userEvent.click(screen.getByRole('button', { name: '创建教师' }));
    await userEvent.type(screen.getByLabelText('教师姓名'), '李老师');
    await userEvent.type(screen.getByLabelText('用户名'), 'li02');
    await userEvent.click(screen.getByRole('button', { name: '确认创建' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('用户名已存在');
    expect(screen.getByLabelText('教师姓名')).toHaveValue('李老师');
    expect(screen.getByLabelText('用户名')).toHaveValue('li02');
  });

  it('confirms disabling and sends the exact account status', async () => {
    api.adminUsers.updateStatus.mockResolvedValue({ ...teacher, status: 'DISABLED' });
    renderPage();

    await screen.findAllByText('王老师');
    await userEvent.click(screen.getAllByRole('button', { name: '停用王老师' })[0]);
    expect(screen.getByText(/现有登录会话将被撤销/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认停用' }));

    expect(api.adminUsers.updateStatus).toHaveBeenCalledWith('teacher-1', 'DISABLED');
  });

  it('resets a password and shows the replacement credential', async () => {
    api.adminUsers.resetPassword.mockResolvedValue(undefined);
    renderPage();

    await screen.findAllByText('王老师');
    await userEvent.click(screen.getAllByRole('button', { name: '重置王老师密码' })[0]);
    expect(screen.getByText(/下次登录后必须修改密码/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认重置' }));

    expect(api.adminUsers.resetPassword).toHaveBeenCalledWith('teacher-1', 'Abcd2345Efgh6789');
    expect(await screen.findByRole('heading', { name: '一次性登录凭据' })).toBeInTheDocument();
    expect(screen.getByText('Abcd2345Efgh6789')).toBeInTheDocument();
  });

  it('offers a retry when the account list fails', async () => {
    api.adminUsers.list.mockImplementation(({ page_size: pageSize }) => (
      pageSize === 20 ? Promise.reject(new Error('教师账号加载失败')) : Promise.resolve(userPage([], 0, 1))
    ));
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('教师账号加载失败');
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });
});
