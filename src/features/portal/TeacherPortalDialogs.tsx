import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { useToast } from '../../components/ToastProvider';
import type { StudentVisibility } from '../../api/portal-types';
import type { Student } from '../../api/types';

export function StudentVisibilityDialog({ classId, onClose }: { classId: string; onClose(): void }) {
  const api = useApi(); const toast = useToast(); const client = useQueryClient();
  const query = useQuery({ queryKey: ['student-visibility', classId], queryFn: () => api.portal.visibility(classId) });
  const [draft, setDraft] = useState<StudentVisibility | null>(null);
  const value = draft ?? query.data;
  const save = useMutation({ mutationFn: () => api.portal.setVisibility(classId, value!), onSuccess: () => {
    void client.invalidateQueries({ queryKey: ['student-visibility', classId] }); toast.show('学生查看权限已保存'); onClose();
  } });
  return <Dialog title="学生查看设置" description="仅控制本班学生查看本人数据，不影响教师录入。" onClose={() => { if (!save.isPending) onClose(); }} footer={<><button className="btn btn-secondary" disabled={save.isPending} onClick={onClose}>取消</button><button className="btn btn-primary" disabled={!value || save.isPending || query.isError} onClick={() => save.mutate()}>{save.isPending ? '正在保存...' : '保存设置'}</button></>}>
    {query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={query.error.message} retry={() => void query.refetch()} /> : value && <div className="form-grid">
      <label className="field"><span>考勤数据</span><select value={String(value.attendance_visible)} disabled={save.isPending} onChange={(e) => setDraft({ ...value, attendance_visible: e.target.value === 'true' })}><option value="false">不可查看</option><option value="true">可查看本人记录</option></select></label>
      <label className="field"><span>平时分数据</span><select value={value.score_visibility} disabled={save.isPending} onChange={(e) => setDraft({ ...value, score_visibility: e.target.value as StudentVisibility['score_visibility'] })}><option value="HIDDEN">不可查看</option><option value="TOTAL">仅查看总分</option><option value="DETAILS">查看总分及明细</option></select></label>
      <p className="form-note">新班级默认不开放。关闭后，学生无法继续查询相应数据；此前已查看的信息无法收回。</p>
    </div>}
    {save.error && <div role="alert" className="form-alert">{save.error.message}</div>}
  </Dialog>;
}

export function StudentAccountDialog({ classId, student, onClose }: { classId: string; student: Student; onClose(): void }) {
  const api = useApi(); const [password, setPassword] = useState(''); const [username, setUsername] = useState('');
  const save = useMutation({ mutationFn: () => api.portal.createAccount(classId, student.id, password), onSuccess: (data) => { setPassword(''); setUsername(data.username); } });
  return <Dialog title="开通学生账号" description={`${student.name} · ${student.student_number}`} onClose={() => { if (!save.isPending) onClose(); }} footer={<button className="btn btn-secondary" onClick={onClose} disabled={save.isPending}>{username ? '完成' : '取消'}</button>}>
    {username ? <p>账号已开通，登录用户名：<strong>{username}</strong>。请单独告知学生初始密码，首次登录必须修改密码。同一账号可查看本人各班级已开放的数据。</p> : <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <label className="field"><span>初始密码</span><input type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={save.isPending} /></label><p className="form-note">12～128 个字符，首次登录必须修改。已有学生账号无需重复开通，重置密码请联系管理员。</p>
      {save.error && <div className="form-alert" role="alert">{save.error.message}</div>}<button className="btn btn-primary" disabled={save.isPending}>{save.isPending ? '正在开通...' : '确认开通'}</button>
    </form>}
  </Dialog>;
}
