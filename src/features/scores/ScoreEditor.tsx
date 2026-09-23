import { Pencil, Plus, Save, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import type { ScoreBook, ScoreCategory, ScoreItem, ScoreSettings, ScoreStudent } from '../../api/scores-types';
import { useApi } from '../../app/auth';
import { EmptyState } from '../../components/AsyncState';
import { useToast } from '../../components/ToastProvider';
import { ScoreItemDialog, ScoreHistoryDialog } from './ScoreDialogs';
import { ScoreSummaryView } from './ScoreSummaryView';
import { categories, decimal, displayPoints, validDecimal } from './score-utils';
import { discardMessage } from './useUnsavedScores';

type RowDraft = { points: string; note: string };
type Tab = 'entry' | 'settings' | 'summary';
export function ScoreEditor({ book, onBook, onDirty }: { book: ScoreBook; onBook(book: ScoreBook): void; onDirty(dirty: boolean): void }) {
  const api = useApi(); const toast = useToast();
  const [tab, setTab] = useState<Tab>('entry'); const [category, setCategory] = useState<ScoreCategory>('HOMEWORK');
  const [selectedItemId, setSelectedItemId] = useState(''); const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const [settingsDraft, setSettingsDraft] = useState<ScoreSettings | null>(null);
  const settings = settingsDraft ?? book.settings;
  const [recordVersion, setRecordVersion] = useState(book.version); const [settingsVersion, setSettingsVersion] = useState(book.version);
  const [itemDialog, setItemDialog] = useState<ScoreItem | 'new' | null>(null); const [itemDirty, setItemDirty] = useState(false);
  const [history, setHistory] = useState<ScoreStudent | null>(null);
  const [pending, setPending] = useState(false); const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false); const [reloaded, setReloaded] = useState(false);
  const [studentSearch, setStudentSearch] = useState('');
  const items = book.items.filter((item) => item.category === category);
  const item = items.find((row) => row.id === selectedItemId) ?? items[0];
  const settingsDirty = settingsDraft !== null;
  const dirty = Object.keys(drafts).length > 0 || settingsDirty || itemDirty;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  const locked = book.readonly || pending;
  function original(enrollmentId: string): RowDraft { const row = book.records.find((record) => record.item_id === item?.id && record.enrollment_id === enrollmentId); return { points: row ? (row.points ?? '') : (item?.default_points ?? ''), note: row?.note ?? '' }; }
  function updateRow(enrollmentId: string, update: Partial<RowDraft>) {
    if (item) setSelectedItemId(item.id);
    if (!Object.keys(drafts).length) setRecordVersion(book.version);
    const source = original(enrollmentId); const next = { ...(drafts[enrollmentId] ?? source), ...update };
    setDrafts((previous) => { const result = { ...previous }; if (next.points === source.points && next.note === source.note) delete result[enrollmentId]; else result[enrollmentId] = next; return result; });
  }
  function setSettings(value: ScoreSettings) { if (!settingsDirty) setSettingsVersion(book.version); setSettingsDraft(value); }
  function discard() { setDrafts({}); setSettingsDraft(null); setError(''); setConflict(false); setReloaded(false); setRecordVersion(book.version); setSettingsVersion(book.version); }
  function switchView(action: () => void) { if (dirty && !window.confirm(discardMessage)) return; discard(); action(); }
  function failed(reason: unknown) {
    if (reason instanceof ApiError && reason.status === 409) { setConflict(true); setReloaded(false); setError(reason.code.includes('VERSION') ? '成绩版本已更新，当前输入已保留。请刷新并核对最新记录，确认后再保存。' : `${reason.message}。当前输入已保留，请刷新并核对班级和名单状态。`); }
    else setError((reason as Error).message || '保存失败，请重试；当前输入已保留。');
  }
  async function refreshConflict() {
    setPending(true);
    try { const latest = await api.scores.get(book.class_group.id); onBook(latest); if (tab !== 'settings') setSettingsDraft(null); setReloaded(true); setError('已加载最新版本。当前草稿仍保留，请对照最新记录和规则，核对后再保存。'); }
    catch (reason) { setError((reason as Error).message); } finally { setPending(false); }
  }
  async function saveRows() {
    if (!item || conflict || book.readonly) return;
    if (Object.values(drafts).some((row) => !validDecimal(row.points))) { setError('请输入有效积分，最多保留四位小数。'); return; }
    if (Object.keys(drafts).some((id) => book.students.find((student) => student.enrollment_id === id)?.enrollment_status !== 'ACTIVE')) { setError('草稿中有已移除学生，历史积分只读。请放弃本次草稿后重新录入在班学生。'); return; }
    const records = Object.entries(drafts).map(([enrollment_id, row]) => ({ enrollment_id, points: decimal(row.points), note: row.note }));
    setPending(true); setError('');
    try { const updated = await api.scores.saveRecords(book.class_group.id, item.id, { expected_version: recordVersion, records }); onBook(updated); setSettingsDraft(null); setDrafts({}); toast.show('本次积分已保存'); }
    catch (reason) { failed(reason); } finally { setPending(false); }
  }
  async function saveSettings() {
    if (conflict || book.readonly) return;
    if (!validDecimal(settings.base_score ?? '') || Object.values(settings.factors).some((value) => !validDecimal(value ?? '', true))) { setError('基础分和系数最多四位小数，换算系数须为非负数。'); return; }
    setPending(true); setError('');
    try { const updated = await api.scores.saveSettings(book.class_group.id, { ...settings, expected_version: settingsVersion }); onBook(updated); setSettingsDraft(null); toast.show('基础分与换算规则已保存'); }
    catch (reason) { failed(reason); } finally { setPending(false); }
  }
  const students = book.students.filter((student) => student.enrollment_status === 'ACTIVE' || book.records.some((record) => record.item_id === item?.id && record.enrollment_id === student.enrollment_id));
  const normalizedSearch = studentSearch.trim().toLocaleLowerCase();
  const matchesSearch = (student: ScoreStudent) => `${student.student_number} ${student.student_name}`.toLocaleLowerCase().includes(normalizedSearch);
  const visibleStudents = normalizedSearch ? students.filter(matchesSearch) : students;
  const visibleSummaryStudents = normalizedSearch ? book.students.filter(matchesSearch) : book.students;
  return <>
    <nav className="scores-tabs" aria-label="平时成绩页面">{([{ key: 'entry', label: '项目积分录入' }, { key: 'settings', label: '基础分与换算' }, { key: 'summary', label: '平时成绩汇总' }] as const).map((option) => <button className={`btn ${tab === option.key ? 'btn-primary' : 'btn-secondary'}`} key={option.key} aria-pressed={tab === option.key} disabled={pending} onClick={() => switchView(() => setTab(option.key))}>{option.label}</button>)}</nav>
    <div className={`scores-notice ${book.rules_ready ? '' : 'warning'}`} role="status">{book.readonly ? '课程或班级已归档：成绩只读，可查看和导出。' : book.rules_ready ? `本班基础分 ${displayPoints(book.settings.base_score)} 分。类别不设上下限，最终平时成绩按 0～100 分展示。` : '规则待配置：可以继续记录积分，设置基础分和全部换算系数后再生成正式汇总。'}</div>
    <label className="search-field scores-student-search"><Search aria-hidden="true" /><span className="sr-only">按学号或姓名搜索</span><input value={studentSearch} onChange={(event) => setStudentSearch(event.target.value)} placeholder="输入学号或姓名" /></label>
    {error && <div className="form-alert" role="alert">{error}{conflict && <div className="actions"><button className="btn btn-secondary" disabled={pending} onClick={() => void refreshConflict()}>刷新并核对</button>{reloaded && <button className="btn btn-secondary" onClick={() => { setRecordVersion(book.version); setSettingsVersion(book.version); setConflict(false); setError(''); }}>确认核对，继续保存</button>}</div>}</div>}
    {tab === 'entry' && <>
      <div className="scores-categories">{categories.map((option) => <button key={option.key} className={`scores-category ${category === option.key ? 'selected' : ''}`} aria-pressed={category === option.key} disabled={pending} onClick={() => switchView(() => { setCategory(option.key); setSelectedItemId(''); })}><strong>{option.label}</strong><small>{book.items.filter((row) => row.category === option.key).length} 个项目 · {book.settings.factors[option.key] == null ? '系数待配置' : `1 积分 = ${book.settings.factors[option.key]} 分`}</small></button>)}</div>
      <div className="scores-project-bar"><label className="field"><span>当前项目</span><select value={item?.id ?? ''} disabled={pending || !items.length} onChange={(e) => switchView(() => setSelectedItemId(e.target.value))}>{!items.length && <option value="">暂无项目</option>}{items.map((row) => <option value={row.id} key={row.id}>{row.name} · {row.occurred_on}</option>)}</select></label><div className="actions"><button className="btn btn-secondary" disabled={locked || conflict || !item} onClick={() => switchView(() => setItemDialog(item!))}><Pencil />编辑项目</button><button className="btn btn-primary" disabled={locked || conflict} onClick={() => switchView(() => setItemDialog('new'))}><Plus />新建项目</button></div></div>
      {!item ? <EmptyState title="该类别还没有评分项目" description="创建作业、实验或表现事件项目，即可先记录积分，稍后设置换算规则。" /> : <>
        {item.description && <p className="form-note">{item.description}</p>}
        <p className="form-note">快捷评分为 1、2、3、4、5；也可输入自定义正负小数。待评价项目默认按 0 分计入汇总，仍保留待评价状态。</p>
        {!visibleStudents.length ? <EmptyState title={students.length ? '没有匹配的学生' : '还没有学生'} description={students.length ? '调整学号或姓名搜索条件。' : '请先在学生名单中导入本班学生。'} /> : <form onSubmit={(event) => { event.preventDefault(); void saveRows(); }}>
          <div className="panel table-scroll"><table className="scores-entry-table"><thead><tr><th>学生</th><th>本次积分</th><th>快捷评价</th><th>备注</th><th>类别累计（已保存）</th><th>状态 / 历史</th></tr></thead><tbody>{visibleStudents.map((student) => {
            const source = original(student.enrollment_id); const row = drafts[student.enrollment_id] ?? source; const removed = student.enrollment_status === 'REMOVED'; const disabled = locked || removed;
            const total = book.summaries.find((summary) => summary.enrollment_id === student.enrollment_id)?.categories.find((group) => group.category === category)?.points;
            return <tr key={student.enrollment_id}><td><strong>{student.student_name}</strong><small>{student.student_number}{removed ? ' · 已移除' : ''}</small></td><td><input className="scores-point" type="number" step="0.0001" aria-label={`${student.student_name}本次积分`} disabled={disabled} value={row.points === '' ? '0' : row.points} placeholder="0" onChange={(event) => updateRow(student.enrollment_id, { points: event.target.value })} />{reloaded && drafts[student.enrollment_id] && <small>最新：{source.points || '0'}</small>}</td><td><div className="scores-quick">{['1', '2', '3', '4', '5'].map((point) => <button type="button" className={`btn btn-secondary btn-sm ${Number(row.points === '' ? '0' : row.points) === Number(point) ? 'chosen' : ''}`} key={point} disabled={disabled} onClick={() => updateRow(student.enrollment_id, { points: point })}>{point}</button>)}</div></td><td><input className="scores-note" aria-label={`${student.student_name}备注`} maxLength={500} disabled={disabled} value={row.note} placeholder="选填" onChange={(event) => updateRow(student.enrollment_id, { note: event.target.value })} />{reloaded && drafts[student.enrollment_id] && <small>最新备注：{source.note || '无'}</small>}</td><td className="mono">{displayPoints(total)}</td><td><small>{removed ? '历史记录 · 只读' : drafts[student.enrollment_id] ? '未保存' : row.points === '' ? '尚未评价' : '已评价'}</small><button type="button" className="btn btn-ghost btn-sm" onClick={() => setHistory(student)}>变更历史</button></td></tr>;
          })}</tbody></table></div>
          <div className="scores-footer"><p>同一项目重复录入为修改，不重复累计。{Object.keys(drafts).length ? ` ${Object.keys(drafts).length} 名学生待保存。` : ''}</p><button className="btn btn-primary" disabled={locked || conflict || !Object.keys(drafts).length}><Save />{pending ? '正在保存...' : '保存本次录入'}</button></div>
        </form>}
      </>}
    </>}
    {tab === 'settings' && <form onSubmit={(event) => { event.preventDefault(); void saveSettings(); }}>
      <div className="scores-base"><label className="field"><span>基础分</span><input type="number" step="0.0001" value={settings.base_score ?? ''} disabled={locked} placeholder="稍后设置" onChange={(event) => setSettings({ ...settings, base_score: decimal(event.target.value) })} /></label><p>默认 70 分，可自行修改。没有加扣积分时，从这个分数起算。</p></div>
      <div className="panel table-scroll"><table className="scores-rules"><thead><tr><th>类别</th><th>每 1 积分折合</th><th>计算方式</th><th>类别上限</th></tr></thead><tbody>{categories.map((option) => <tr key={option.key}><td><strong>{option.label}</strong></td><td><input type="number" min="0" step="0.0001" aria-label={`${option.label}每积分分值`} disabled={locked} placeholder="稍后设置" value={settings.factors[option.key] ?? ''} onChange={(event) => setSettings({ ...settings, factors: { ...settings.factors, [option.key]: decimal(event.target.value) } })} /> 分</td><td>净积分 × 换算系数</td><td>不限</td></tr>)}</tbody></table></div>
      {reloaded && <p className="form-note">最新基础分：{book.settings.base_score ?? '待配置'}；{categories.map((option) => `${option.label}系数 ${book.settings.factors[option.key] ?? '待配置'}`).join('；')}</p>}
      <div className="scores-formula"><strong>平时成绩 = 基础分 + 各类别净积分 × 对应换算系数</strong><p>系数无需合计 100；0 表示该类别不参与计算，留空表示尚未配置。只限制最终总成绩在 0～100 分，保留限制前的原始总分。</p><p>保存规则后重新计算汇总，已录入的原始积分保持不变。考勤单独管理。</p></div>
      <div className="scores-footer"><p>{settingsDirty ? '规则有未保存修改' : '规则已与服务器同步'}</p><button className="btn btn-primary" disabled={locked || conflict || !settingsDirty}><Save />保存换算规则</button></div>
    </form>}
    {tab === 'summary' && <ScoreSummaryView book={book} students={visibleSummaryStudents} onHistory={setHistory} />}
    {itemDialog && <ScoreItemDialog book={book} initial={itemDialog === 'new' ? undefined : itemDialog} category={category} onDirty={setItemDirty} close={() => { if (!itemDirty || window.confirm(discardMessage)) { setItemDialog(null); setItemDirty(false); } }} done={(updated, id) => { onBook(updated); setSettingsDraft(null); setCategory(updated.items.find((row) => row.id === id)?.category ?? category); setSelectedItemId(id); setItemDialog(null); setItemDirty(false); toast.show('项目已保存'); }} />}
    {history && <ScoreHistoryDialog book={book} student={history} close={() => setHistory(null)} />}
  </>;
}
