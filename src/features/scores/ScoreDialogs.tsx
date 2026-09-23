import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import type { ScoreBook, ScoreCategory, ScoreItem, ScoreStudent } from '../../api/scores-types';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { categories, validDecimal } from './score-utils';

export function ScoreItemDialog({ book, initial, category, close, done, onDirty }: { book: ScoreBook; initial?: ScoreItem; category: ScoreCategory; close(): void; done(book: ScoreBook, itemId: string): void; onDirty(dirty: boolean): void }) {
  const api = useApi(); const [name, setName] = useState(initial?.name ?? ''); const [kind, setKind] = useState(category);
  const [initialDate] = useState(initial?.occurred_on ?? new Date().toLocaleDateString('sv-SE'));
  const [date, setDate] = useState(initialDate);
  const [description, setDescription] = useState(initial?.description ?? '');
  const [defaultPoints, setDefaultPoints] = useState(initial?.default_points ?? '0');
  const [error, setError] = useState(''); const [pending, setPending] = useState(false); const [latest, setLatest] = useState(book); const [conflict, setConflict] = useState(false); const [reloaded, setReloaded] = useState(false);
  useEffect(() => { onDirty(name !== (initial?.name ?? '') || description !== (initial?.description ?? '') || kind !== category || date !== initialDate || defaultPoints !== (initial?.default_points ?? '0')); }, [name, description, kind, date, defaultPoints, initial, initialDate, category, onDirty]);
  async function submit() {
    if (!name.trim() || !date || !defaultPoints.trim() || !validDecimal(defaultPoints) || conflict || latest.readonly) return;
    setPending(true); setError('');
    try {
      const input = { expected_version: latest.version, name: name.trim(), occurred_on: date, description, default_points: defaultPoints.trim() || null };
      const updated = initial ? await api.scores.updateItem(book.class_group.id, initial.id, input) : await api.scores.createItem(book.class_group.id, { ...input, category: kind });
      const itemId = initial?.id ?? updated.items.find((row) => !latest.items.some((old) => old.id === row.id))?.id ?? '';
      done(updated, itemId);
    } catch (reason) { if (reason instanceof ApiError && reason.status === 409) { setConflict(true); setReloaded(false); setError(`${reason.message}。项目输入已保留，请刷新并核对后继续。`); } else setError((reason as Error).message); }
    finally { setPending(false); }
  }
  async function reload() { setPending(true); try { setLatest(await api.scores.get(book.class_group.id)); setReloaded(true); } catch (reason) { setError((reason as Error).message); } finally { setPending(false); } }
  const serverItem = latest.items.find((row) => row.id === initial?.id);
  return <Dialog title={initial ? '编辑项目' : '新建项目'} description={`${book.course.name} · ${book.class_group.name}`} onClose={() => { if (!pending) close(); }} footer={<><button className="btn btn-secondary" disabled={pending} onClick={close}>取消</button><button className="btn btn-primary" form="score-item-form" disabled={pending || conflict || latest.readonly}>{initial ? '保存项目' : '创建项目'}</button></>}>
    <form id="score-item-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <label className="field"><span>所属类别</span><select disabled={Boolean(initial) || pending} value={kind} onChange={(event) => setKind(event.target.value as ScoreCategory)}>{categories.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}</select></label>
      <label className="field"><span>项目名称</span><input required maxLength={120} disabled={pending} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：实验 1 · 环境搭建" /></label>
      <label className="field"><span>项目日期</span><input required type="date" disabled={pending} value={date} onChange={(event) => setDate(event.target.value)} /></label>
      <label className="field"><span>项目默认积分</span><input aria-label="项目默认积分" required type="number" step="0.0001" disabled={pending} value={defaultPoints} onChange={(event) => setDefaultPoints(event.target.value)} /><small>仅用于新建项目时初始化学生分值，之后修改不会覆盖已保存的学生分值。</small></label>
      <label className="field"><span>项目说明</span><textarea rows={3} maxLength={500} disabled={pending} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
      {error && <div className="form-alert" role="alert">{error}{conflict && <><button type="button" className="btn btn-secondary" disabled={pending} onClick={() => void reload()}>刷新并核对</button>{reloaded && <><p>最新项目：{serverItem ? `${serverItem.name} · ${serverItem.occurred_on} · ${serverItem.description || '无说明'}` : '项目尚未创建'}{latest.readonly ? '；班级已归档，只读' : ''}</p><button type="button" className="btn btn-secondary" onClick={() => { setConflict(false); setError(''); }}>确认核对，继续保存</button></>}</>}</div>}
    </form>
  </Dialog>;
}

function historyValue(value: Record<string, unknown> | null, book: ScoreBook) {
  if (!value) return '无记录';
  const labels: Record<string, string> = { points: '积分', note: '备注', name: '项目名称', category: '类别', occurred_on: '日期', description: '说明', default_points: '项目默认积分', base_score: '基础分', factors: '系数', item_id: '项目', enrollment_id: '名单成员' };
  return Object.entries(value).filter(([key]) => key in labels).map(([key, data]) => {
    const shown = key === 'item_id' ? book.items.find((item) => item.id === data)?.name ?? data : key === 'category' ? categories.find((item) => item.key === data)?.label ?? data : data;
    return `${labels[key]}：${shown === null ? '尚未评价' : typeof shown === 'object' ? JSON.stringify(shown) : String(shown ?? '')}`;
  }).join('；') || '记录已更新';
}
export function ScoreHistoryDialog({ book, student, close }: { book: ScoreBook; student: ScoreStudent; close(): void }) {
  const api = useApi(); const query = useQuery({ queryKey: ['scores-history', book.class_group.id, student.enrollment_id, book.version], queryFn: () => api.scores.history(book.class_group.id, student.enrollment_id) });
  return <Dialog title="成绩变更历史" description={`${student.student_name} · ${student.student_number}`} onClose={close}>
    {query.isLoading ? <LoadingState label="正在加载变更历史..." /> : query.error ? <ErrorState message={query.error.message} retry={() => void query.refetch()} /> : !query.data?.items.length ? <EmptyState title="暂无变更记录" description="积分保存后会记录修改前后内容及操作人。" /> : <ol className="scores-history">{query.data.items.map((row) => <li key={row.id}><strong>{row.actor_name || '教师'}</strong><time>{new Date(row.created_at).toLocaleString('zh-CN')}</time><p>修改前：{historyValue(row.before_value, book)}</p><p>修改后：{historyValue(row.after_value, book)}</p></li>)}</ol>}
  </Dialog>;
}
