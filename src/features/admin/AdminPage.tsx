import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Copy,
  KeyRound,
  LogOut,
  MoreHorizontal,
  Plus,
  Search,
  ShieldCheck,
  UserCheck,
  UserRound,
  UserX,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { CreateTeacherInput, User, UserStatus } from '../../api/types';
import { useApi, useAuth } from '../../app/auth';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { Dialog } from '../../components/Dialog';
import { Pagination } from '../../components/Pagination';
import { useToast } from '../../components/ToastProvider';
import { generateTemporaryPassword } from './temporary-password';

type AdminDialog =
  | { kind: 'create'; password: string }
  | { kind: 'status'; user: User }
  | { kind: 'reset'; user: User; password: string }
  | { kind: 'credentials'; displayName: string; username: string; password: string }
  | null;

function normalizedPage(raw: string | null) {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : 1;
}

function normalizedStatus(raw: string | null): UserStatus | undefined {
  return raw === 'ACTIVE' || raw === 'DISABLED' ? raw : undefined;
}

function lastLoginLabel(value: string | null) {
  if (!value) return '从未登录';
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value));
}

export function AdminPage() {
  const api = useApi();
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [dialog, setDialog] = useState<AdminDialog>(null);
  const page = normalizedPage(params.get('page'));
  const q = params.get('q') ?? '';
  const status = normalizedStatus(params.get('status'));
  const listParams = {
    role: 'TEACHER' as const,
    page,
    page_size: 20,
    q: q || undefined,
    status,
  };

  const list = useQuery({
    queryKey: ['admin-users', listParams],
    queryFn: () => api.adminUsers.list(listParams),
  });
  const allCount = useQuery({
    queryKey: ['admin-user-count', 'ALL'],
    queryFn: () => api.adminUsers.list({ role: 'TEACHER', page: 1, page_size: 1 }),
  });
  const activeCount = useQuery({
    queryKey: ['admin-user-count', 'ACTIVE'],
    queryFn: () => api.adminUsers.list({ role: 'TEACHER', status: 'ACTIVE', page: 1, page_size: 1 }),
  });
  const disabledCount = useQuery({
    queryKey: ['admin-user-count', 'DISABLED'],
    queryFn: () => api.adminUsers.list({ role: 'TEACHER', status: 'DISABLED', page: 1, page_size: 1 }),
  });

  async function refreshUsers() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
      queryClient.invalidateQueries({ queryKey: ['admin-user-count'] }),
    ]);
  }

  const createTeacher = useMutation({
    mutationFn: (input: CreateTeacherInput) => api.adminUsers.create(input),
    onSuccess: async (created, input) => {
      await refreshUsers();
      setDialog({
        kind: 'credentials',
        displayName: created.display_name,
        username: created.username,
        password: input.temporary_password,
      });
    },
  });
  const updateStatus = useMutation({
    mutationFn: ({ account, nextStatus }: { account: User; nextStatus: UserStatus }) => (
      api.adminUsers.updateStatus(account.id, nextStatus)
    ),
    onSuccess: async (updated) => {
      await refreshUsers();
      setDialog(null);
      toast.show(updated.status === 'ACTIVE' ? '教师账号已启用' : '教师账号已停用');
    },
  });
  const resetPassword = useMutation({
    mutationFn: ({ account, password }: { account: User; password: string }) => (
      api.adminUsers.resetPassword(account.id, password).then(() => ({ account, password }))
    ),
    onSuccess: async ({ account, password }) => {
      await refreshUsers();
      setDialog({
        kind: 'credentials',
        displayName: account.display_name,
        username: account.username,
        password,
      });
    },
  });

  function updateParam(key: 'q' | 'status' | 'page', value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.set('page', '1');
    setParams(next, { replace: true });
  }

  const accounts = list.data?.items ?? [];
  return <main className="admin-page">
    <header className="admin-topbar">
      <div className="brand"><span className="brand-mark" aria-hidden="true">课</span><span>课点</span></div>
      <div className="admin-session">
        <span><strong>{user?.display_name}</strong><small>{user?.username}</small></span>
        <button className="btn btn-secondary" type="button" onClick={() => void logout()}><LogOut aria-hidden="true" />退出登录</button>
      </div>
    </header>
    <section className="admin-content" aria-labelledby="admin-title">
      <div className="admin-page-header">
        <div className="admin-identity">
          <span className="admin-shield" aria-hidden="true"><ShieldCheck /></span>
          <div><p className="eyebrow">系统管理</p><h1 id="admin-title">教师账号</h1><p>创建并维护教师登录资格。</p></div>
        </div>
        <button className="btn btn-primary" type="button" onClick={() => setDialog({ kind: 'create', password: generateTemporaryPassword() })}><Plus aria-hidden="true" />创建教师</button>
      </div>

      <div className="metrics-grid admin-summary" aria-label="教师账号统计">
        <article className="metric" aria-label="教师账号总数"><UserRound aria-hidden="true" /><span>账号总数</span><strong>{allCount.data?.total ?? '-'}</strong></article>
        <article className="metric" aria-label="启用教师数"><UserCheck aria-hidden="true" /><span>已启用</span><strong>{activeCount.data?.total ?? '-'}</strong></article>
        <article className="metric" aria-label="停用教师数"><UserX aria-hidden="true" /><span>已停用</span><strong>{disabledCount.data?.total ?? '-'}</strong></article>
      </div>

      <div className="toolbar admin-toolbar">
        <label className="search-field"><span>搜索教师</span><Search aria-hidden="true" /><input value={q} onChange={(event) => updateParam('q', event.target.value)} placeholder="输入姓名或用户名" /></label>
        <label><span>账号状态</span><select value={status ?? ''} onChange={(event) => updateParam('status', event.target.value)}><option value="">全部状态</option><option value="ACTIVE">已启用</option><option value="DISABLED">已停用</option></select></label>
      </div>

      {list.isLoading ? <LoadingState label="正在加载教师账号..." /> : list.error ? <ErrorState message={list.error.message} retry={() => void list.refetch()} /> : accounts.length === 0 ? <EmptyState title="没有匹配的教师账号" description="调整搜索或筛选条件，也可以创建新的教师账号。" action={<button className="btn btn-primary" type="button" onClick={() => setDialog({ kind: 'create', password: generateTemporaryPassword() })}><Plus aria-hidden="true" />创建教师</button>} /> : <>
        <div className="panel admin-table table-scroll">
          <table>
            <thead><tr><th>教师</th><th>用户名</th><th>账号状态</th><th>密码状态</th><th>最近登录</th><th><span className="sr-only">账号操作</span></th></tr></thead>
            <tbody>{accounts.map((account) => <tr key={account.id}>
              <td><strong>{account.display_name}</strong></td>
              <td className="mono">{account.username}</td>
              <td><StatusBadge account={account} /></td>
              <td>{account.must_change_password ? <span className="status pending">首次登录需改密</span> : <span className="status active">密码已设置</span>}</td>
              <td>{lastLoginLabel(account.last_login_at)}</td>
              <td><AccountActions account={account} onStatus={() => setDialog({ kind: 'status', user: account })} onReset={() => setDialog({ kind: 'reset', user: account, password: generateTemporaryPassword() })} /></td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className="admin-mobile-list">{accounts.map((account) => <article className="admin-account" key={account.id}>
          <header><div><strong>{account.display_name}</strong><small className="mono">{account.username}</small></div><StatusBadge account={account} /></header>
          <dl><div><dt>密码状态</dt><dd>{account.must_change_password ? '首次登录需改密' : '密码已设置'}</dd></div><div><dt>最近登录</dt><dd>{lastLoginLabel(account.last_login_at)}</dd></div></dl>
          <details className="admin-account-menu"><summary aria-label={`管理${account.display_name}`}><MoreHorizontal aria-hidden="true" />账号操作</summary><AccountActions account={account} onStatus={() => setDialog({ kind: 'status', user: account })} onReset={() => setDialog({ kind: 'reset', user: account, password: generateTemporaryPassword() })} /></details>
        </article>)}</div>
        <Pagination page={page} pageSize={list.data?.page_size ?? 20} total={list.data?.total ?? 0} onChange={(value) => updateParam('page', String(value))} />
      </>}
    </section>

    {dialog?.kind === 'create' && <TeacherFormDialog password={dialog.password} pending={createTeacher.isPending} onClose={() => setDialog(null)} onSubmit={(input) => createTeacher.mutateAsync(input)} />}
    {dialog?.kind === 'status' && <StatusDialog account={dialog.user} pending={updateStatus.isPending} onClose={() => setDialog(null)} onConfirm={(nextStatus) => updateStatus.mutateAsync({ account: dialog.user, nextStatus })} />}
    {dialog?.kind === 'reset' && <ResetPasswordDialog account={dialog.user} pending={resetPassword.isPending} onClose={() => setDialog(null)} onConfirm={() => resetPassword.mutateAsync({ account: dialog.user, password: dialog.password })} />}
    {dialog?.kind === 'credentials' && <CredentialsDialog displayName={dialog.displayName} username={dialog.username} password={dialog.password} onClose={() => setDialog(null)} />}
  </main>;
}

function StatusBadge({ account }: { account: User }) {
  return <span className={`status ${account.status === 'ACTIVE' ? 'active' : 'archived'}`}>{account.status === 'ACTIVE' ? '已启用' : '已停用'}</span>;
}

function AccountActions({ account, onStatus, onReset }: { account: User; onStatus(): void; onReset(): void }) {
  return <div className="account-actions">
    <button className="btn btn-secondary btn-sm" type="button" onClick={onReset} aria-label={`重置${account.display_name}密码`}><KeyRound aria-hidden="true" />重置密码</button>
    <button className="btn btn-ghost btn-sm" type="button" onClick={onStatus} aria-label={`${account.status === 'ACTIVE' ? '停用' : '启用'}${account.display_name}`}>{account.status === 'ACTIVE' ? <UserX aria-hidden="true" /> : <UserCheck aria-hidden="true" />}{account.status === 'ACTIVE' ? '停用' : '启用'}</button>
  </div>;
}

function TeacherFormDialog({ password, pending, onClose, onSubmit }: { password: string; pending: boolean; onClose(): void; onSubmit(input: CreateTeacherInput): Promise<unknown> }) {
  const [displayName, setDisplayName] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    const normalizedName = displayName.trim();
    const normalizedUsername = username.trim().toLowerCase();
    if (!normalizedName || !normalizedUsername) {
      setError('请完整填写教师姓名和用户名');
      return;
    }
    setError('');
    try {
      await onSubmit({ display_name: normalizedName, username: normalizedUsername, temporary_password: password });
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  return <Dialog title="创建教师" description="系统会自动生成仅显示一次的临时密码。" onClose={onClose} footer={<><button className="btn btn-secondary" type="button" onClick={onClose}>取消</button><button className="btn btn-primary" type="submit" form="teacher-form" disabled={pending}>确认创建</button></>}>
    <form id="teacher-form" onSubmit={submit}>
      <label className="field"><span>教师姓名</span><input autoFocus maxLength={100} value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="off" /></label>
      <label className="field"><span>用户名</span><input maxLength={64} value={username} onChange={(event) => setUsername(event.target.value)} autoCapitalize="none" autoComplete="off" /></label>
      <p className="form-note">创建后教师需使用临时密码登录，并立即设置自己的新密码。</p>
      {error && <div className="form-alert" role="alert">{error}</div>}
    </form>
  </Dialog>;
}

function StatusDialog({ account, pending, onClose, onConfirm }: { account: User; pending: boolean; onClose(): void; onConfirm(status: UserStatus): Promise<unknown> }) {
  const [error, setError] = useState('');
  const disabling = account.status === 'ACTIVE';
  async function confirm() {
    setError('');
    try { await onConfirm(disabling ? 'DISABLED' : 'ACTIVE'); }
    catch (reason) { setError((reason as Error).message); }
  }
  return <Dialog title={`${disabling ? '停用' : '启用'}教师账号`} description={`${account.display_name}（${account.username}）`} onClose={onClose} footer={<><button className="btn btn-secondary" type="button" onClick={onClose}>取消</button><button className={`btn ${disabling ? 'btn-danger' : 'btn-primary'}`} type="button" disabled={pending} onClick={() => void confirm()}>确认{disabling ? '停用' : '启用'}</button></>}>
    <p>{disabling ? '停用后教师将无法登录，现有登录会话将被撤销。' : '启用后教师可以继续使用原密码登录。'}</p>
    {error && <div className="form-alert" role="alert">{error}</div>}
  </Dialog>;
}

function ResetPasswordDialog({ account, pending, onClose, onConfirm }: { account: User; pending: boolean; onClose(): void; onConfirm(): Promise<unknown> }) {
  const [error, setError] = useState('');
  async function confirm() {
    setError('');
    try { await onConfirm(); }
    catch (reason) { setError((reason as Error).message); }
  }
  return <Dialog title="重置教师密码" description={`${account.display_name}（${account.username}）`} onClose={onClose} footer={<><button className="btn btn-secondary" type="button" onClick={onClose}>取消</button><button className="btn btn-primary" type="button" disabled={pending} onClick={() => void confirm()}>确认重置</button></>}>
    <p>重置后现有登录会话将被撤销，教师使用新临时密码登录，下次登录后必须修改密码。</p>
    <p className="form-note">新临时密码会在操作成功后显示一次。</p>
    {error && <div className="form-alert" role="alert">{error}</div>}
  </Dialog>;
}

function CredentialsDialog({ displayName, username, password, onClose }: { displayName: string; username: string; password: string; onClose(): void }) {
  const toast = useToast();
  const [error, setError] = useState('');
  async function copyCredentials() {
    const text = `姓名：${displayName}\n用户名：${username}\n临时密码：${password}\n首次登录后请立即修改密码。`;
    try {
      await navigator.clipboard.writeText(text);
      toast.show('登录凭据已复制');
    } catch {
      setError('复制失败，请手动选择并保存凭据');
    }
  }
  return <Dialog title="一次性登录凭据" description="关闭后无法再次查看，只能重置密码。" onClose={onClose} footer={<button className="btn btn-primary" type="button" onClick={onClose}>完成</button>}>
    <dl className="credential-list">
      <div><dt>教师姓名</dt><dd>{displayName}</dd></div>
      <div><dt>用户名</dt><dd className="mono">{username}</dd></div>
      <div><dt>临时密码</dt><dd className="credential-value mono">{password}</dd></div>
    </dl>
    <button className="btn btn-secondary btn-block" type="button" onClick={() => void copyCredentials()}><Copy aria-hidden="true" />复制登录凭据</button>
    <p className="form-note">请通过可信渠道交给教师，并提醒其首次登录后立即修改密码。</p>
    {error && <div className="form-alert" role="alert">{error}</div>}
  </Dialog>;
}
