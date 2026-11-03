import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useApi } from '../../app/auth';
import { ApiError } from '../../api/client';
import type { MonitorProject } from '../../api/monitor-types';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { ScorePointInput } from '../scores/ScorePointInput';
import { decimal, roundPoints, validDecimal } from '../scores/score-utils';
import { discardMessage, useUnsavedScores } from '../scores/useUnsavedScores';
import { useToast } from '../../components/ToastProvider';

export function MonitorPage() {
  const api = useApi(); const { classId = '' } = useParams(); const [selected, setSelected] = useState(''); const [dirty, setDirty] = useState(false); const [saving, setSaving] = useState(false);
  const projects = useQuery({ queryKey: ['monitor-projects'], queryFn: () => api.monitors.projects() });
  const items = projects.data?.items.filter((item) => item.class_id === classId) ?? [];
  const itemId = items.find((item) => item.id === selected)?.id ?? items[0]?.id ?? '';
  const detail = useQuery({ queryKey: ['monitor-project', classId, itemId], queryFn: () => api.monitors.get(classId, itemId), enabled: Boolean(itemId), refetchOnWindowFocus: false, gcTime: 0 });
  useUnsavedScores(dirty);
  return <main className="page" style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}><header className="page-header"><div><p className="eyebrow">班长协助登记</p><h1>授权项目平时分</h1><p>只显示任课老师授权的项目。本人分数由老师填写，所有修改保留操作记录。</p></div><Link className="btn btn-secondary" to="/student">返回个人中心</Link></header>
    {projects.isLoading ? <LoadingState /> : projects.error ? <ErrorState message={projects.error.message} retry={() => void projects.refetch()} /> : !items.length ? <EmptyState title="暂无授权项目" description="请联系任课老师在班长授权管理中指定项目。" /> : <>
      <label className="field"><span>授权项目</span><select disabled={saving} value={itemId} onChange={(e) => { if (dirty && !window.confirm(discardMessage)) return; setDirty(false); setSelected(e.target.value); }}>{items.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.occurred_on}</option>)}</select></label>
      {detail.isLoading ? <LoadingState /> : detail.error ? <ErrorState message={detail.error.message} retry={() => void detail.refetch()} /> : detail.data && <MonitorEditor key={itemId} classId={classId} data={detail.data} onDirty={setDirty} onPending={setSaving} />}
    </>}
  </main>;
}

function MonitorEditor({ classId, data, onDirty, onPending }: { classId: string; data: MonitorProject; onDirty(value: boolean): void; onPending(value: boolean): void }) {
  const api = useApi(); const client = useQueryClient(); const toast = useToast();
  const [drafts, setDrafts] = useState<Record<string, { points: string; note: string }>>({});
  const [version, setVersion] = useState(data.version); const [pending, setPending] = useState(false); const [blocked, setBlocked] = useState(false); const [error, setError] = useState('');
  useEffect(() => { onPending(pending); }, [pending, onPending]);
  const source = (id: string) => { const record = data.records.find((row) => row.enrollment_id === id); return { points: record ? record.points ?? '' : data.item.default_points ?? '', note: record?.note ?? '' }; };
  function update(id: string, change: Partial<{ points: string; note: string }>) {
    if (!Object.keys(drafts).length) setVersion(data.version);
    const original = source(id); const value = { ...(drafts[id] ?? original), ...change }; const next = { ...drafts };
    if (value.points === original.points && value.note === original.note) delete next[id]; else next[id] = value;
    setDrafts(next); onDirty(Boolean(Object.keys(next).length));
  }
  async function save() {
    if (pending || blocked || !Object.keys(drafts).length) return;
    if (Object.values(drafts).some((row) => !validDecimal(row.points))) { setError('请输入有效积分，保存时保留一位小数。'); return; }
    setPending(true); setError('');
    try {
      const updated = await api.monitors.save(classId, data.item.id, { expected_version: version, records: Object.entries(drafts).map(([enrollment_id, row]) => ({ enrollment_id, points: decimal(row.points) === null ? null : roundPoints(row.points), note: row.note })) });
      client.setQueryData(['monitor-project', classId, data.item.id], updated); setVersion(updated.version); setDrafts({}); onDirty(false); toast.show('授权项目积分已保存');
    } catch (reason) { setError(`${(reason as Error).message}。当前输入已保留。`); if (reason instanceof ApiError && (reason.status === 409 || reason.status === 403)) setBlocked(true); }
    finally { setPending(false); }
  }
  async function refresh() {
    if (Object.keys(drafts).length && !window.confirm('刷新将放弃当前草稿，确定重新加载吗？')) return;
    setPending(true);
    try { const updated = await api.monitors.get(classId, data.item.id); client.setQueryData(['monitor-project', classId, data.item.id], updated); setVersion(updated.version); setDrafts({}); onDirty(false); setBlocked(false); setError(''); }
    catch (reason) { setBlocked(true); setError((reason as Error).message); }
    finally { setPending(false); }
  }
  return <form noValidate onSubmit={(e) => { e.preventDefault(); void save(); }}>
    {error && <div className="form-alert" role="alert">{error}</div>}
    {data.item.description && <p>{data.item.description}</p>}
    <div className="panel table-scroll"><table><thead><tr><th>学生</th><th>本次积分</th><th>备注</th><th>状态</th></tr></thead><tbody>{data.students.map((student) => {
      const row = drafts[student.enrollment_id] ?? source(student.enrollment_id); const disabled = pending || blocked || !student.can_edit;
      return <tr key={student.enrollment_id}><td><strong>{student.student_name}</strong><small>{student.student_number}</small></td><td><ScorePointInput label={`${student.student_name}本次积分`} value={row.points} disabled={disabled} onChange={(points) => update(student.enrollment_id, { points })} /></td><td><input aria-label={`${student.student_name}备注`} disabled={disabled} maxLength={500} value={row.note} onChange={(e) => update(student.enrollment_id, { note: e.target.value })} /></td><td>{!student.can_edit ? '本人分数 · 老师登记' : drafts[student.enrollment_id] ? '未保存' : row.points === '' ? '待评价' : '已评价'}</td></tr>;
    })}</tbody></table></div>
    <div className="scores-footer"><button className="btn btn-secondary" type="button" disabled={pending} onClick={() => void refresh()}>刷新项目</button><button className="btn btn-primary" disabled={pending || blocked || !Object.keys(drafts).length}>{pending ? '正在保存...' : '保存本次录入'}</button></div>
  </form>;
}
