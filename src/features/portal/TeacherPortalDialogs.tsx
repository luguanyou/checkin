import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { useToast } from '../../components/ToastProvider';
import type { StudentVisibility } from '../../api/portal-types';
import type { Student } from '../../api/types';
import { generateTemporaryPassword } from '../admin/temporary-password';

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
  const api = useApi(); const [password] = useState(() => generateTemporaryPassword()); const [username, setUsername] = useState('');
  const save = useMutation({ mutationFn: () => api.portal.createAccount(classId, student.id, password), onSuccess: (data) => { setUsername(data.username); } });
  return <Dialog title="开通学生账号" description={`${student.name} · ${student.student_number}`} onClose={() => { if (!save.isPending) onClose(); }} footer={<button className="btn btn-secondary" onClick={onClose} disabled={save.isPending}>{username ? '完成' : '取消'}</button>}>
    {username ? <><p>账号已开通，登录用户名：<strong>{username}</strong>。请单独告知学生临时密码，首次登录必须修改密码。同一账号可查看本人各班级已开放的数据。</p><label className="field"><span>临时密码</span><input readOnly value={password} /></label></> : <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <p className="form-note">确认开通后显示系统随机生成的 8 位数字临时密码，首次登录必须修改。已有账号忘记密码时，请关闭弹窗，点击该学生的「重置密码」。</p>
      {save.error && <div className="form-alert" role="alert">{save.error.message}</div>}<button className="btn btn-primary" disabled={save.isPending}>{save.isPending ? '正在开通...' : '确认开通'}</button>
    </form>}
  </Dialog>;
}

export function StudentPasswordResetDialog({ classId, student, onClose }: { classId: string; student: Student; onClose(): void }) {
  const api = useApi();
  const toast = useToast();
  const [password] = useState(() => generateTemporaryPassword());
  const [copyError, setCopyError] = useState('');
  const reset = useMutation({
    mutationFn: () => api.portal.resetPassword(classId, student.id, password),
  });
  async function copyCredentials() {
    try {
      await navigator.clipboard.writeText(`姓名：${student.name}\n学号：${reset.data!.username}\n临时密码：${password}\n登录后请立即修改密码。`);
      setCopyError('');
      toast.show('登录凭据已复制');
    } catch {
      setCopyError('复制失败，请手动选择并保存凭据');
    }
  }
  return <Dialog title={reset.isSuccess ? '学生密码已重置' : '重置学生密码'} description={`${student.name} · ${student.student_number}`} onClose={() => { if (!reset.isPending) onClose(); }} footer={
    reset.isSuccess ? <button className="btn btn-primary" onClick={onClose}>完成</button> : <>
      <button className="btn btn-secondary" disabled={reset.isPending} onClick={onClose}>取消</button>
      <button className="btn btn-primary" disabled={reset.isPending} onClick={() => reset.mutate()}>{reset.isPending ? '正在重置...' : '确认重置'}</button>
    </>
  }>
    {reset.isSuccess ? <>
      <p>登录学号：<strong>{reset.data.username}</strong></p>
      <label className="field"><span>临时密码</span><input readOnly value={password} /></label>
      <button className="btn btn-secondary" onClick={() => void copyCredentials()}>复制登录凭据</button>
      <p className="form-note">请将临时密码私下交给学生本人，学生登录后必须设置新密码。关闭后无法再次查看此临时密码。</p>
      {copyError && <div className="form-alert" role="alert">{copyError}</div>}
    </> : <>
      <p>请先核对学生本人身份。重置会撤销该学生现有登录会话，学生下次登录必须修改密码。</p>
      <p className="form-note">该学生的所有课程共用一个账号，本次重置对其他课程也生效。</p>
      {reset.error && <div className="form-alert" role="alert">{reset.error.message}</div>}
    </>}
  </Dialog>;
}
