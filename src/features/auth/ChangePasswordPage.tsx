import { useState, type FormEvent } from 'react';
import { useAuth } from '../../app/auth';
import { ApiError } from '../../api/client';

export function ChangePasswordPage() {
  const { changePassword, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState(''); const [newPassword, setNewPassword] = useState(''); const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!currentPassword) return setError('请输入当前密码');
    if (newPassword.length < 12) return setError('新密码至少需要 12 个字符');
    if (newPassword !== confirmation) return setError('两次输入的新密码不一致');
    setPending(true); setError('');
    try { await changePassword(currentPassword, newPassword); } catch (reason) { setError(reason instanceof ApiError ? reason.message : '密码修改失败，请稍后重试'); } finally { setPending(false); }
  }
  return <main className="auth-page"><section className="auth-panel" aria-labelledby="password-title">
    <p className="eyebrow">首次登录</p><h1 id="password-title">设置新密码</h1><p>修改初始密码后才能进入教师工作台。</p>
    <form onSubmit={submit}><label className="field"><span>当前密码</span><input type="password" autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} /></label><label className="field"><span>新密码</span><input type="password" autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></label><label className="field"><span>确认新密码</span><input type="password" autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label>{error && <div className="form-alert" role="alert">{error}</div>}<button className="btn btn-primary btn-block" disabled={pending}>{pending ? '正在保存...' : '保存并进入工作台'}</button><button className="btn btn-ghost btn-block" type="button" onClick={() => void logout()}>退出登录</button></form>
  </section></main>;
}
