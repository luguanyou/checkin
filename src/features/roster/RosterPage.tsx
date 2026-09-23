import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Search, Trash2, Upload, UserMinus, UserPlus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useApi } from '../../app/auth';
import { ErrorState, LoadingState, EmptyState } from '../../components/AsyncState';
import { Pagination } from '../../components/Pagination';
import { useToast } from '../../components/ToastProvider';
import { createRosterTemplate } from './import-utils';
import { ImportRosterDialog } from './ImportRosterDialog';

export function RosterPage() {
  const api = useApi(); const { classId = '' } = useParams(); const navigate = useNavigate(); const queryClient = useQueryClient(); const toast = useToast();
  const [params, setParams] = useSearchParams(); const [showImport, setShowImport] = useState(false);
  const page = Number(params.get('page') || 1); const q = params.get('q') || ''; const status = params.get('status') || 'ACTIVE';
  const context = useQuery({ queryKey: ['courses', 'roster-context'], queryFn: () => api.courses.list({ page_size: 100 }) });
  const actualClassId = classId === 'current' ? context.data?.items.flatMap((course) => course.classes).find((item) => item.status === 'ACTIVE')?.id : classId;
  useEffect(() => { if (classId === 'current' && actualClassId) navigate(`/classes/${actualClassId}/roster`, { replace: true }); }, [actualClassId, classId, navigate]);
  const query = useQuery({ queryKey: ['roster', actualClassId, { page, q, status }], queryFn: () => api.roster.list(actualClassId!, { page, page_size: 20, q: q || undefined, status }), enabled: Boolean(actualClassId) });
  const updateStatus = useMutation({ mutationFn: ({ id, next }: { id: string; next: 'ACTIVE' | 'REMOVED' }) => api.roster.updateStatus(id, next), onSuccess: () => { toast.show('名单成员状态已更新'); void queryClient.invalidateQueries({ queryKey: ['roster', actualClassId] }); } });
  const deleteClass = useMutation({ mutationFn: () => api.courses.deleteClass(actualClassId!, true), onSuccess: () => { toast.show('班级及关联数据已删除'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); navigate('/courses'); }, onError: (reason) => toast.show((reason as Error).message) });
  function update(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); if (key !== 'page') next.set('page', '1'); setParams(next); }
  function downloadTemplate() { const url = URL.createObjectURL(createRosterTemplate()); const anchor = document.createElement('a'); anchor.href = url; anchor.download = '学生名单导入模板.csv'; anchor.click(); URL.revokeObjectURL(url); }
  if (classId === 'current' && context.isLoading) return <LoadingState label="正在查找班级..." />;
  if (!actualClassId) return <EmptyState title="还没有可用班级" description="请先在课程班级页面创建班级。" />;
  if (query.isLoading) return <LoadingState label="正在加载学生名单..." />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;
  const members = query.data?.items ?? [];
  const selectedClass = context.data?.items.flatMap((course) => course.classes.map((item) => ({ ...item, course }))).find((item) => item.id === actualClassId);
  function confirmDeleteClass() { if (window.confirm(`确定删除班级“${selectedClass?.name || '当前班级'}”吗？该班级的学生名单和全部历史考勤记录将永久删除，且无法恢复。平时成绩项目、积分和换算规则也将同时永久删除。`)) deleteClass.mutate(); }
  return <section className="page"><div className="page-header"><div><p className="eyebrow">{selectedClass?.course.name || '班级名单'}</p><h1>{selectedClass?.name || '学生名单'}</h1><p>共 {query.data?.total ?? 0} 名成员</p></div><div className="actions"><button className="btn btn-ghost" aria-label="删除班级" title="删除班级" disabled={deleteClass.isPending} onClick={confirmDeleteClass}><Trash2 />删除班级</button><button className="btn btn-secondary" onClick={downloadTemplate}><Download />下载模板</button><button className="btn btn-primary" onClick={() => setShowImport(true)}><Upload />导入名单</button></div></div>
    <div className="toolbar"><label className="search-field"><Search /><span className="sr-only">搜索名单</span><input value={q} placeholder="搜索姓名、学号或专业" onChange={(e) => update('q', e.target.value)} /></label><label><span className="sr-only">成员状态</span><select value={status} onChange={(e) => update('status', e.target.value)}><option value="ACTIVE">当前成员</option><option value="REMOVED">已移除</option><option value="all">全部成员</option></select></label></div>
    {!members.length ? <EmptyState title="没有匹配的学生" description="调整搜索条件，或导入新的学生名单。" /> : <div className="panel table-scroll"><table><thead><tr><th>学号</th><th>姓名</th><th>性别</th><th>专业</th><th>状态</th><th>操作</th></tr></thead><tbody>{members.map((member) => <tr key={member.enrollment_id}><td className="mono">{member.student.student_number}</td><td><strong>{member.student.name}</strong></td><td>{member.student.gender || '-'}</td><td>{member.student.major || '-'}</td><td><span className={`status ${member.enrollment_status.toLowerCase()}`}>{member.enrollment_status === 'ACTIVE' ? '在名单中' : '已移除'}</span></td><td><button className="btn btn-ghost btn-sm" disabled={updateStatus.isPending} onClick={() => updateStatus.mutate({ id: member.enrollment_id, next: member.enrollment_status === 'ACTIVE' ? 'REMOVED' : 'ACTIVE' })}>{member.enrollment_status === 'ACTIVE' ? <><UserMinus />移除</> : <><UserPlus />恢复</>}</button></td></tr>)}</tbody></table></div>}
    <Pagination page={page} pageSize={query.data?.page_size ?? 20} total={query.data?.total ?? 0} onChange={(value) => update('page', String(value))} />
    {showImport && <ImportRosterDialog classId={actualClassId} onClose={() => setShowImport(false)} />}
  </section>;
}
