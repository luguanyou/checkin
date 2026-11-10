import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useApi, useAuth } from '../../app/auth';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { useToast } from '../../components/ToastProvider';

const labels = { PENDING: '待审核', APPROVED: '已通过', REJECTED: '已驳回' };
export function RegistrationReviewPage() {
  const api = useApi(); const { user } = useAuth(); const { classId = '' } = useParams(); const client = useQueryClient(); const toast = useToast();
  const [status, setStatus] = useState('all'); const [selected, setSelected] = useState<string[]>([]); const [reason, setReason] = useState('');
  // Applications arrive from other sessions; a cached empty list must be refreshed.
  const query = useQuery({
    queryKey: ['registrations', classId, status],
    queryFn: () => api.registrations.list(classId, status),
    staleTime: 0,
    refetchInterval: 15_000,
  });
  const applications = (query.data?.items ?? []).slice().sort((a, b) => Number(b.status === 'PENDING') - Number(a.status === 'PENDING'));
  const actionable = applications.filter((item) => item.can_review); const batch = actionable.slice(0, 100);
  const selectedIds = selected.filter((id) => actionable.some((row) => row.id === id));
  const mutation = useMutation({ mutationFn: ({ ids, decision }: { ids: string[]; decision: 'APPROVED'|'REJECTED' }) => api.registrations.review(classId, ids, decision, reason.trim() || undefined), onSuccess: async (result) => {
    setSelected([]);
    setReason('');
    await Promise.all([
      client.invalidateQueries({ queryKey: ['registrations'] }),
      client.invalidateQueries({ queryKey: ['monitor-management'] }),
    ]);
    toast.show(`已处理 ${result.reviewed} 条注册申请`);
  } });
  return <section className="page" style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
    <header className="page-header"><div><p className="eyebrow">班级账号管理</p><h1>学生注册审核</h1><p>核对本人身份后再通过。通过将开通学生统一账号，不能查看或设置其密码。</p></div><Link className="btn btn-secondary" to={user?.role === 'TEACHER' ? `/classes/${classId}/roster` : '/student'}>返回班级</Link></header>
    <div className="toolbar"><label className="field"><span>申请状态</span><select disabled={mutation.isPending} value={status} onChange={(e) => { setStatus(e.target.value); setSelected([]); mutation.reset(); }}><option value="PENDING">待审核</option><option value="APPROVED">已通过</option><option value="REJECTED">已驳回</option><option value="all">全部申请</option></select></label><button className="btn btn-secondary" disabled={mutation.isPending} onClick={() => void query.refetch()}>{query.isFetching ? '正在刷新…' : '刷新申请'}</button></div>
    {mutation.error && <div className="form-alert" role="alert">{mutation.error.message}</div>}
    {query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={query.error.message} retry={() => void query.refetch()} /> : !query.data?.items.length ? <EmptyState title="暂无匹配的注册申请" description={status === 'all' ? '学生可在登录页提交注册申请，新申请会自动刷新。' : '可切换到全部申请查看其他状态的记录。'} /> : <>
      <label className="field"><span>审核备注（选填，驳回时向学生说明原因）</span><input maxLength={500} disabled={mutation.isPending} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      <p className="form-note">每批最多审核 100 条；不能审核本人申请。</p><div className="actions" style={{ marginBottom: 16 }}><button className="btn btn-primary" disabled={!selectedIds.length || mutation.isPending} onClick={() => mutation.mutate({ ids: selectedIds, decision: 'APPROVED' })}>通过所选（{selectedIds.length}）</button><button className="btn btn-secondary" disabled={!selectedIds.length || mutation.isPending} onClick={() => mutation.mutate({ ids: selectedIds, decision: 'REJECTED' })}>驳回所选</button></div>
      <div className="panel table-scroll"><table><thead><tr><th><input aria-label="全选待审核申请" type="checkbox" disabled={!actionable.length || mutation.isPending} checked={batch.length > 0 && batch.every((item) => selectedIds.includes(item.id))} onChange={(e) => setSelected(e.target.checked ? batch.map((item) => item.id) : [])} /></th><th>学号 / 姓名</th><th>提交时间</th><th>状态</th><th>审核人 / 备注</th><th>操作</th></tr></thead><tbody>{applications.map((item) => <tr key={item.id}>
        <td><input type="checkbox" aria-label={`选择${item.name}的申请`} checked={selectedIds.includes(item.id)} disabled={!item.can_review || mutation.isPending || (selectedIds.length >= 100 && !selectedIds.includes(item.id))} onChange={(e) => setSelected(e.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} /></td><td><strong>{item.name}</strong><small>{item.student_number}</small></td><td>{new Date(`${item.created_at}Z`).toLocaleString('zh-CN')}</td><td>{labels[item.status]}</td><td>{item.reviewer_name || '—'}<small>{item.reason}</small>{Boolean(item.history?.length) && <details><summary>审核历史（{item.history!.length}）</summary>{item.history!.map((event, index) => <p key={index}>{event.reviewer_name} · {labels[event.status]} · {new Date(`${event.created_at}Z`).toLocaleString('zh-CN')}{event.reason ? ` · ${event.reason}` : ''}</p>)}</details>}</td><td>{item.can_review ? <div className="actions"><button className="btn btn-primary btn-sm" disabled={mutation.isPending} onClick={() => mutation.mutate({ ids: [item.id], decision: 'APPROVED' })}>通过</button><button className="btn btn-secondary btn-sm" disabled={mutation.isPending} onClick={() => mutation.mutate({ ids: [item.id], decision: 'REJECTED' })}>驳回</button></div> : item.status === 'PENDING' ? '本人申请，不可自审' : '已处理'}</td>
      </tr>)}</tbody></table></div>
    </>}
  </section>;
}
