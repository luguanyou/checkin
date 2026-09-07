import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Download, FileSpreadsheet, Pencil } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useApi } from '../../app/auth';
import type { AttendanceRecord, AttendanceStatus } from '../../api/types';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { Dialog } from '../../components/Dialog';
import { useToast } from '../../components/ToastProvider';

const labels: Record<AttendanceStatus, string> = { pending: '待确认', present: '已到', absent: '缺勤', leave: '请假', late: '迟到' };
export function RecordDetailPage() {
  const { sessionId = '' } = useParams(); const api = useApi(); const toast = useToast(); const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['session', sessionId], queryFn: () => api.attendance.get(sessionId) });
  const [record, setRecord] = useState<AttendanceRecord | null>(null); const [format, setFormat] = useState<'csv' | 'xlsx' | null>(null); const [exporting, setExporting] = useState(false);
  if (query.isLoading) return <LoadingState label="正在加载场次详情..." />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;
  if (!query.data) return null; const session = query.data;
  async function download() { if (!format) return; setExporting(true); try { const file = await api.attendance.export(sessionId, format); const url = URL.createObjectURL(file.blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = file.filename; anchor.click(); URL.revokeObjectURL(url); setFormat(null); toast.show('导出文件已生成'); } catch (reason) { toast.show((reason as Error).message, 'error'); } finally { setExporting(false); } }
  return <section className="page"><div className="page-header"><div><Link className="back-link" to="/records"><ArrowLeft />返回记录</Link><h1>{session.course.name}</h1><p>{session.class_group.name} · {session.session_date}</p></div><button className="btn btn-primary" onClick={() => setFormat('xlsx')}><Download />导出记录</button></div>
    <div className="metrics-grid record-metrics"><article className="metric"><span>应到</span><strong>{session.summary.total}</strong></article><article className="metric present"><span>已到</span><strong>{session.summary.present}</strong></article><article className="metric absent"><span>缺勤</span><strong>{session.summary.absent}</strong></article><article className="metric late"><span>迟到</span><strong>{session.summary.late}</strong></article></div>
    <div className="panel table-scroll"><table><thead><tr><th>学号</th><th>姓名</th><th>状态</th><th>标记时间</th><th>最后修改</th><th>操作</th></tr></thead><tbody>{session.records.map((item) => <tr key={item.id}><td className="mono">{item.student_number}</td><td><strong>{item.student_name}</strong></td><td><span className={`status ${item.status}`}>{labels[item.status]}</span></td><td>{formatTime(item.marked_at)}</td><td>{item.last_modified_by.display_name}<small>{formatTime(item.last_modified_at)}</small></td><td><button className="btn btn-ghost btn-sm" onClick={() => setRecord(item)}><Pencil />修正</button></td></tr>)}</tbody></table></div>
    {record && <CorrectionDialog record={record} completed={session.status === 'COMPLETED'} close={() => setRecord(null)} done={(updated) => { queryClient.setQueryData(['session', sessionId], { ...session, records: session.records.map((item) => item.id === updated.id ? updated : item) }); setRecord(null); toast.show('考勤状态已修正'); }} />}
    {format && <Dialog title="导出考勤记录" description={`${session.course.name} · ${session.class_group.name}`} onClose={() => setFormat(null)} footer={<><button className="btn btn-secondary" onClick={() => setFormat(null)}>取消</button><button className="btn btn-primary" disabled={exporting} onClick={() => void download()}>生成文件</button></>}><div className="format-options"><label className={format === 'xlsx' ? 'selected' : ''}><input type="radio" checked={format === 'xlsx'} onChange={() => setFormat('xlsx')} /><FileSpreadsheet />Excel 工作簿 (.xlsx)</label><label className={format === 'csv' ? 'selected' : ''}><input type="radio" checked={format === 'csv'} onChange={() => setFormat('csv')} /><FileSpreadsheet />CSV 文本 (.csv)</label></div></Dialog>}
  </section>;
}

function CorrectionDialog({ record, completed, close, done }: { record: AttendanceRecord; completed: boolean; close(): void; done(record: AttendanceRecord): void }) {
  const api = useApi(); const [status, setStatus] = useState<Exclude<AttendanceStatus, 'pending'>>(record.status === 'pending' ? 'present' : record.status); const [reason, setReason] = useState(''); const [error, setError] = useState('');
  const mutation = useMutation({ mutationFn: () => api.attendance.updateRecord(record.id, { status, expected_version: record.version, client_mutation_id: crypto.randomUUID(), reason: reason.trim() || undefined }), onSuccess: done, onError: (value) => setError(value.message) });
  function submit(event: FormEvent) { event.preventDefault(); if (completed && !reason.trim()) return setError('请填写修正原因'); mutation.mutate(); }
  return <Dialog title="修正考勤状态" description={`${record.student_name} · ${record.student_number}`} onClose={close} footer={<><button className="btn btn-secondary" onClick={close}>取消</button><button className="btn btn-primary" form="correction-form" disabled={mutation.isPending}>确认修正</button></>}><form id="correction-form" onSubmit={submit}><label className="field"><span>考勤状态</span><select value={status} onChange={(e) => setStatus(e.target.value as Exclude<AttendanceStatus, 'pending'>)}><option value="present">已到</option><option value="absent">缺勤</option><option value="leave">请假</option><option value="late">迟到</option></select></label>{completed && <label className="field"><span>修正原因</span><textarea rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="说明本次修正依据" /></label>}{error && <div className="form-alert" role="alert">{error}</div>}</form></Dialog>;
}
function formatTime(value: string | null) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '-'; }
