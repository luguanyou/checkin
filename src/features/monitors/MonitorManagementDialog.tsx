import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { useToast } from '../../components/ToastProvider';
import { StudentAccountDialog } from '../portal/TeacherPortalDialogs';

export function MonitorManagementDialog({ classId, onClose }: { classId: string; onClose(): void }) {
  const api = useApi(); const client = useQueryClient(); const toast = useToast();
  const query = useQuery({ queryKey: ['monitor-management', classId], queryFn: () => api.monitors.manage(classId) });
  const [reviewDraft, setReviewDraft] = useState<boolean | null>(null); const [studentId, setStudentId] = useState(''); const [draft, setDraft] = useState<string[] | null>(null); const [createAccount, setCreateAccount] = useState(false);
  const member = query.data?.members.find((row) => row.student.id === studentId) ?? query.data?.members[0];
  const selected = draft ?? member?.item_ids ?? []; const canReview = reviewDraft ?? member?.can_review_registrations ?? false;
  const save = useMutation({ mutationFn: ({ itemIds, review }: { itemIds: string[]; review: boolean }) => review || member?.can_review_registrations ? api.monitors.setGrants(classId, member!.user_id!, itemIds, review) : api.monitors.setGrants(classId, member!.user_id!, itemIds), onSuccess: (data) => { client.setQueryData(['monitor-management', classId], data); setDraft(null); setReviewDraft(null); toast.show('班长授权已更新'); }, });
  if (createAccount && member) return <StudentAccountDialog classId={classId} student={member.student} onClose={() => { setCreateAccount(false); void query.refetch(); }} />;
  const cannotGrant = query.data?.readonly || member?.enrollment_status !== 'ACTIVE' || member?.account_status !== 'ACTIVE';
  return <Dialog title="班长授权管理" description="使用学生账号，成绩代录和注册审核分别授权，可只开启其中一项。" onClose={() => { if (!save.isPending) onClose(); }} footer={<><button className="btn btn-secondary" disabled={save.isPending} onClick={onClose}>关闭</button><button className="btn btn-secondary" disabled={!member?.user_id || (!member.item_ids.length && !member.can_review_registrations) || save.isPending} onClick={() => save.mutate({ itemIds: [], review: false })}>撤销全部授权</button><button className="btn btn-primary" disabled={!member?.user_id || save.isPending || (Boolean(cannotGrant) && (selected.length > 0 || canReview))} onClick={() => save.mutate({ itemIds: selected, review: canReview })}>{save.isPending ? '正在保存...' : '保存授权'}</button></>}>
    {query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={query.error.message} retry={() => void query.refetch()} /> : !member ? <EmptyState title="暂无学生" description="请先在班级名单中新增或导入学生。" /> : <>
      <label className="field"><span>选择学生 / 班长</span><select disabled={save.isPending} value={member.student.id} onChange={(e) => { setStudentId(e.target.value); setDraft(null); setReviewDraft(null); save.reset(); }}>{query.data?.members.map((row) => <option key={row.student.id} value={row.student.id}>{row.student.name} · {row.student.student_number}{row.item_ids.length ? ` · 已授权 ${row.item_ids.length} 个项目` : ''}{row.can_review_registrations ? ' · 可审核注册' : ''}{row.enrollment_status !== 'ACTIVE' ? ' · 已移除' : ''}</option>)}</select></label>
      {!member.user_id ? <div><p>该学生尚未开通账号，请先开通再授权。</p><button className="btn btn-secondary" disabled={query.data?.readonly || member.enrollment_status !== 'ACTIVE'} onClick={() => setCreateAccount(true)}>开通学生账号</button></div> : <p>登录账号：{member.username} · {member.account_status === 'ACTIVE' ? '已启用' : '已停用，请联系管理员启用'}</p>}
      <label style={{ display: 'flex', gap: 8, padding: '12px 0' }}><input type="checkbox" checked={canReview} disabled={Boolean(cannotGrant) || !member.user_id || save.isPending} onChange={(e) => setReviewDraft(e.target.checked)} />允许审核本班学生注册</label>
      <fieldset disabled={Boolean(cannotGrant) || !member.user_id || save.isPending}><legend>允许查看和编辑的项目</legend>{!query.data?.items.length ? <p>暂无项目，请老师先在平时成绩中创建项目。</p> : query.data.items.map((item) => <label key={item.id} style={{ display: 'flex', gap: 8, padding: '8px 0' }}><input type="checkbox" checked={selected.includes(item.id)} onChange={(e) => setDraft(e.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} />{item.name} · {item.occurred_on}</label>)}</fieldset>
      <p className="form-note">班长只能执行已勾选的权限，不能转授权限、审核自己或修改本人分数。移出名单、停用账号、归档班级后权限失效；永久取消代录资格请撤销授权。</p>
      {save.error && <div className="form-alert" role="alert">{save.error.message}</div>}
    </>}
  </Dialog>;
}
