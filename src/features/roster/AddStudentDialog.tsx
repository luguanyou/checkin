import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';
import { useToast } from '../../components/ToastProvider';
import type { RosterMember } from '../../api/types';

export function AddStudentDialog({ classId, member, onClose, onSaved }: { classId: string; member?: RosterMember; onClose(): void; onSaved(): void }) {
  const api = useApi(); const queryClient = useQueryClient(); const toast = useToast();
  const [number, setNumber] = useState(member?.student.student_number ?? ''); const [name, setName] = useState(member?.student.name ?? '');
  const [gender, setGender] = useState(member?.student.gender ?? ''); const [major, setMajor] = useState(member?.student.major ?? '');
  const formId = member ? 'edit-student-form' : 'add-student-form';
  const [error, setError] = useState('');
  const save = useMutation({
    mutationFn: () => {
      const input = { student_number: number.trim(), name: name.trim(), gender: gender || undefined, major: major.trim() || undefined };
      return member ? api.roster.update(classId, member.enrollment_id, input) : api.roster.create(classId, input);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['roster'] });
      void queryClient.invalidateQueries({ queryKey: ['courses'] });
      void queryClient.invalidateQueries({ queryKey: ['scores'] });
      void queryClient.invalidateQueries({ queryKey: ['monitor-management'] });
      void queryClient.invalidateQueries({ queryKey: ['monitor-project'] });
      toast.show(member ? '学生资料已保存' : '学生已加入当前班级'); onSaved(); onClose();
    },
    onError: (reason) => setError(reason.message),
  });
  return <Dialog title={member ? '编辑学生资料' : '新增学生'} description={member ? '资料会同步到该学生所在的其他班级，历史考勤快照保留。修改学号会同步学生登录账号。' : '填写学生信息并加入当前班级。已移除的成员将恢复，已有学号将沿用原学生资料。'} onClose={() => { if (!save.isPending) onClose(); }} footer={<><button className="btn btn-secondary" disabled={save.isPending} onClick={onClose}>取消</button><button type="submit" form={formId} className="btn btn-primary" disabled={save.isPending}>{save.isPending ? '正在保存...' : '保存'}</button></>}>
    <form id={formId} className="student-form" onSubmit={(event) => { event.preventDefault(); if (save.isPending) return; if (!number.trim() || !name.trim()) { setError('请填写学号和姓名'); return; } setError(''); save.mutate(); }}>
      <label className="field"><span>学号</span><input required placeholder="请输入学号" maxLength={50} value={number} onChange={(event) => setNumber(event.target.value)} disabled={save.isPending} /></label>
      <label className="field"><span>姓名</span><input required placeholder="请输入姓名" maxLength={100} value={name} onChange={(event) => setName(event.target.value)} disabled={save.isPending} /></label>
      <label className="field"><span>性别</span><select value={gender} onChange={(event) => setGender(event.target.value)} disabled={save.isPending}><option value="">未填写</option><option>男</option><option>女</option></select></label>
      <label className="field"><span>专业</span><input placeholder="选填" maxLength={120} value={major} onChange={(event) => setMajor(event.target.value)} disabled={save.isPending} /></label>
      {error && <div className="form-alert" role="alert">{error}</div>}
    </form>
  </Dialog>;
}
