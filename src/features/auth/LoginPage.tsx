import { useState, type FormEvent } from 'react';
import { LockKeyhole, UserRound } from 'lucide-react';
import { useAuth } from '../../app/auth';
import { ApiError } from '../../api/client';

export function LoginPage() {
  const { login } = useAuth(); const [username, setUsername] = useState(''); const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({}); const [serverError, setServerError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); const next: Record<string, string> = {};
    if (!username.trim()) next.username = '请输入用户名';
    if (!password) next.password = '请输入密码';
    setErrors(next); if (Object.keys(next).length) return;
    setPending(true); setServerError('');
    try { await login(username.trim(), password); } catch (error) { setServerError(error instanceof ApiError ? error.message : '暂时无法登录，请稍后重试'); } finally { setPending(false); }
  }
  return <main className="auth-page"><section className="auth-panel" aria-labelledby="login-title">
    <div className="auth-brand"><span aria-hidden="true">课</span><strong>课点</strong></div>
    <div className="auth-copy"><p className="eyebrow">教师工作台</p><h1 id="login-title">登录课点</h1><p>进入课程、名单与课堂点名。</p></div>
    <form onSubmit={submit} noValidate>
      <label className="field"><span>用户名</span><span className="input-wrap"><UserRound aria-hidden="true" /><input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} aria-invalid={Boolean(errors.username)} /></span>{errors.username && <small className="field-error">{errors.username}</small>}</label>
      <label className="field"><span>密码</span><span className="input-wrap"><LockKeyhole aria-hidden="true" /><input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={Boolean(errors.password)} /></span>{errors.password && <small className="field-error">{errors.password}</small>}</label>
      {serverError && <div className="form-alert" role="alert">{serverError}</div>}
      <button className="btn btn-primary btn-block" type="submit" disabled={pending}>{pending ? '正在登录...' : '登录'}</button>
    </form>
  </section></main>;
}
