import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../components/ToastProvider';
import { LoginPage } from './LoginPage';

const { login } = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock('../../app/auth', () => ({ useAuth: () => ({ login }) }));
const key = 'kaoqing:remember-password';
beforeEach(() => { localStorage.clear(); login.mockReset().mockResolvedValue({}); });
afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); });
function showLogin() { return render(<MemoryRouter><ToastProvider><LoginPage /></ToastProvider></MemoryRouter>); }
async function enterCredentials() {
  await userEvent.type(screen.getByLabelText('用户名'), 'teacher');
  await userEvent.type(screen.getByLabelText('密码'), 'saved-password');
}

it('defaults to not remembering', () => {
  showLogin();
  expect(screen.getByRole('checkbox', { name: '记住密码' })).not.toBeChecked();
});

it('restores both fields on the next visit after a successful opted-in login without browser password APIs', async () => {
  const first = showLogin();
  await enterCredentials();
  await userEvent.click(screen.getByRole('checkbox', { name: '记住密码' }));
  expect(localStorage.getItem(key)).toBeNull();
  await userEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(login).toHaveBeenCalledWith('teacher', 'saved-password'));
  first.unmount(); showLogin();
  expect(screen.getByRole('checkbox', { name: '记住密码' })).toBeChecked();
  expect(screen.getByLabelText('用户名')).toHaveValue('teacher');
  expect(screen.getByLabelText('密码')).toHaveValue('saved-password');
});

it('clears saved credentials immediately when unchecked, even without logging in', async () => {
  localStorage.setItem(key, JSON.stringify({ username: 'teacher', password: 'saved-password' }));
  const first = showLogin();
  await userEvent.click(screen.getByRole('checkbox', { name: '记住密码' }));
  expect(localStorage.getItem(key)).toBeNull();
  first.unmount(); showLogin();
  expect(screen.getByLabelText('用户名')).toHaveValue('');
  expect(screen.getByLabelText('密码')).toHaveValue('');
});

it('never saves a rejected password', async () => {
  login.mockRejectedValue(new Error('failed'));
  showLogin(); await enterCredentials();
  await userEvent.click(screen.getByRole('checkbox', { name: '记住密码' }));
  await userEvent.click(screen.getByRole('button', { name: '登录' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法登录');
  expect(localStorage.getItem(key)).toBeNull();
});

it('does not save credentials when remembering is off', async () => {
  showLogin(); await enterCredentials();
  await userEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(login).toHaveBeenCalled());
  expect(localStorage.getItem(key)).toBeNull();
});

it.each(['true', '{broken', 'null', '{"username":42,"password":"test"}'])('ignores legacy or damaged saved data: %s', (value) => {
  localStorage.setItem(key, value); showLogin();
  expect(screen.getByRole('checkbox', { name: '记住密码' })).not.toBeChecked();
  expect(screen.getByLabelText('用户名')).toHaveValue('');
});

it('reports a storage failure without failing authentication', async () => {
  showLogin(); await enterCredentials();
  await userEvent.click(screen.getByRole('checkbox', { name: '记住密码' }));
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  await userEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(login).toHaveBeenCalled());
  expect(await screen.findByText('登录成功，但浏览器未能保存账号密码，请检查浏览器存储设置。')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
