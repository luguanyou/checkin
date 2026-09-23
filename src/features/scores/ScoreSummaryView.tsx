import { Download } from 'lucide-react';
import { useState } from 'react';
import type { ScoreBook, ScoreStudent } from '../../api/scores-types';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';
import { EmptyState } from '../../components/AsyncState';
import { useToast } from '../../components/ToastProvider';
import { categories, displayPoints, displayScore, scoreStatus } from './score-utils';

export function ScoreSummaryView({ book, students = book.students, onHistory }: { book: ScoreBook; students?: ScoreStudent[]; onHistory(student: ScoreStudent): void }) {
  const api = useApi(); const toast = useToast();
  const [kind, setKind] = useState<'summary' | 'details' | null>(null); const [format, setFormat] = useState<'csv' | 'xlsx'>('xlsx'); const [pending, setPending] = useState(false); const [error, setError] = useState('');
  async function download() {
    if (!kind) return; setPending(true); setError('');
    try { const file = await api.scores.export(book.class_group.id, format, kind); const url = URL.createObjectURL(file.blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = file.filename; anchor.click(); URL.revokeObjectURL(url); setKind(null); toast.show('成绩导出文件已生成'); }
    catch (reason) { setError((reason as Error).message); } finally { setPending(false); }
  }
  return <>
    <div className="scores-summary-head"><div><h2>本班成绩汇总</h2><p>保留原始积分与限制前总分，方便核对。</p></div><div className="actions"><button className="btn btn-secondary" onClick={() => { setError(''); setKind('details'); }}><Download />导出原始明细</button><button className="btn btn-primary" disabled={!book.rules_ready} onClick={() => { setError(''); setKind('summary'); }}><Download />导出正式汇总</button></div></div>
    <div className="metrics-grid scores-overview"><article className="metric"><span>本班基础分</span><strong>{book.settings.base_score == null ? '待配置' : displayPoints(book.settings.base_score)}</strong></article><article className="metric"><span>各类别积分与加扣分</span><strong>不设上下限</strong></article><article className="metric"><span>最终平时成绩</span><strong>100 分制</strong></article></div>
    {!students.length ? <EmptyState title={book.students.length ? '没有匹配的学生' : '还没有学生成绩'} description={book.students.length ? '调整学号或姓名搜索条件。' : '导入名单并录入项目积分后，可在此查看汇总。'} /> : <div className="panel table-scroll"><table className="scores-summary-table"><thead><tr><th>学生</th><th>基础分</th>{categories.map((option) => <th key={option.key}>{option.label}加扣分</th>)}<th>原始总分</th><th>最终成绩</th><th>状态</th></tr></thead><tbody>{students.map((student) => {
      const summary = book.summaries.find((row) => row.enrollment_id === student.enrollment_id);
      return <tr key={student.enrollment_id}><td><button className="scores-student-link" onClick={() => onHistory(student)}>{student.student_name}</button><small>{student.student_number}{student.enrollment_status === 'REMOVED' ? ' · 已移除' : ''}</small></td><td>{displayPoints(book.settings.base_score)}</td>{categories.map((option) => {
        const group = summary?.categories.find((row) => row.category === option.key); const disabled = book.settings.factors[option.key] !== null && Number(book.settings.factors[option.key]) === 0;
        return <td key={option.key}><strong>{disabled ? '不计入' : displayScore(group?.contribution)}</strong><small>{displayPoints(group?.points)} 净积分{group?.pending ? ` · ${group.pending} 项待评` : ''}</small></td>;
      })}<td>{displayScore(summary?.raw_score)}</td><td className="scores-final">{displayScore(summary?.final_score)}{summary?.raw_score != null && summary.final_score != null && Number(summary.raw_score) !== Number(summary.final_score) && <small>{Number(summary.raw_score) > 100 ? '封顶 100 分' : '最低 0 分'}</small>}</td><td><span className={`status ${summary?.status === 'READY' ? 'active' : 'pending'}`}>{summary ? scoreStatus[summary.status] : '待评完整'}</span></td></tr>;
    })}</tbody></table></div>}
    <p className="form-note">考勤不参与平时成绩。待评价项目按 0 分计入汇总，并保留待评价状态提示；规则待配置时可导出原始明细。</p>
    {kind && <Dialog title="导出平时成绩" description={`${book.course.name} · ${book.class_group.name} · ${kind === 'summary' ? '正式汇总' : '原始明细'}`} onClose={() => { if (!pending) setKind(null); }} footer={<><button className="btn btn-secondary" disabled={pending} onClick={() => setKind(null)}>取消</button><button className="btn btn-primary" disabled={pending} onClick={() => void download()}>生成文件</button></>}><div className="format-options"><label className={format === 'xlsx' ? 'selected' : ''}><input type="radio" name="score-export-format" checked={format === 'xlsx'} onChange={() => setFormat('xlsx')} />Excel 工作簿 (.xlsx)</label><label className={format === 'csv' ? 'selected' : ''}><input type="radio" name="score-export-format" checked={format === 'csv'} onChange={() => setFormat('csv')} />CSV 文本 (.csv)</label></div>{error && <div role="alert" className="form-alert">{error}</div>}</Dialog>}
  </>;
}
