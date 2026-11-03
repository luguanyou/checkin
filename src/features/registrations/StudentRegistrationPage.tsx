import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../../app/auth';
import type { RegistrationClass } from '../../api/registration-types';

export function StudentRegistrationPage() {
  const api = useApi(); const [number, setNumber] = useState(''); const [name, setName] = useState('');
  const [classes, setClasses] = useState<RegistrationClass[] | null>(null); const [classId, setClassId] = useState('');
  const [password, setPassword] = useState(''); const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false); const [error, setError] = useState(''); const [submitted, setSubmitted] = useState(false);
  async function submit() {
    if (pending) return;
    setError('');
    if (!number.trim() || !name.trim()) { setError('请填写学号和姓名'); return; }
    if (classes && (password.length < 12 || password.length > 128)) { setError('密码需为 12～128 个字符'); return; }
    if (classes && password !== confirmation) { setError('两次输入的密码不一致'); return; }
    setPending(true);
    try {
      if (!classes) {
        const result = await api.registrations.lookup(number.trim(), name.trim());
        if (!result.items.length) { setError('没有可申请的有效班级，请联系任课老师'); return; }
        setClasses(result.items); setClassId(result.items[0].id);
      } else {
        await api.registrations.register({ student_number: number.trim(), name: name.trim(), class_id: classId, password });
        setPassword(''); setConfirmation(''); setSubmitted(true);
      }
    } catch (reason) { setError((reason as Error).message); }
    finally { setPending(false); }
  }
  return <main className="auth-page"><section className="auth-panel" aria-labelledby="register-title">
    <div className="auth-brand"><span aria-hidden="true">课</span><strong>课点</strong></div><h1 id="register-title">学生注册</h1>
    {submitted ? <><p role="status">申请已提交，等待任课老师或获授权班长审核。通过后使用学号和刚设置的密码登录。</p><p>审核结果可在登录时查看。申请未通过时，核对资料后可重新申请。</p><Link className="btn btn-primary btn-block" to="/login">返回登录</Link></> : <>
      <p>先匹配班级名单，再自行设置密码。审核通过后才能登录。</p>
      <form onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <label className="field"><span>学号</span><input autoComplete="username" required maxLength={50} value={number} disabled={pending || classes !== null} onChange={(e) => setNumber(e.target.value)} /></label>
        <label className="field"><span>姓名</span><input autoComplete="name" required maxLength={100} value={name} disabled={pending || classes !== null} onChange={(e) => setName(e.target.value)} /></label>
        {classes && <>
          <label className="field"><span>申请班级</span><select required value={classId} disabled={pending} onChange={(e) => setClassId(e.target.value)}>{classes.map((item) => <option value={item.id} key={item.id}>{item.course_name} · {item.name} · {item.term}</option>)}</select></label>
          <label className="field"><span>设置密码</span><input type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={pending} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          <label className="field"><span>确认密码</span><input type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={pending} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label>
          <p className="form-note">审核人员会核对本人身份。账号统一开通后，可查看本人各班级已开放的数据；不会自动获得班长权限。</p>
        </>}
        {error && <div className="form-alert" role="alert">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={pending}>{pending ? '正在处理...' : classes ? '提交注册申请' : '匹配班级名单'}</button>
        {classes && <button type="button" className="btn btn-ghost btn-block" disabled={pending} onClick={() => { setClasses(null); setClassId(''); setPassword(''); setConfirmation(''); setError(''); }}>重新匹配名单</button>}
      </form><Link className="btn btn-ghost btn-block" to="/login">已有账号，返回登录</Link>
    </>}
  </section></main>;
}
