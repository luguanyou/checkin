import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, FileSpreadsheet, Upload } from 'lucide-react';
import { useState } from 'react';
import { useApi } from '../../app/auth';
import type { ImportPreview, ImportResult } from '../../api/types';
import { Dialog } from '../../components/Dialog';
import { previewStatusLabel, validateRosterFile } from './import-utils';

export function ImportRosterDialog({ classId, onClose }: { classId: string; onClose(): void }) {
  const api = useApi(); const queryClient = useQueryClient();
  const [preview, setPreview] = useState<ImportPreview | null>(null); const [result, setResult] = useState<ImportResult | null>(null);
  const [policy, setPolicy] = useState<'skip' | 'replace'>('skip'); const [error, setError] = useState('');
  const upload = useMutation({ mutationFn: (file: File) => api.roster.preview(classId, file), onSuccess: setPreview, onError: (reason) => setError(reason.message) });
  const confirm = useMutation({ mutationFn: () => api.roster.confirm(classId, preview!.preview_id, policy), onSuccess: (value) => { setResult(value); void queryClient.invalidateQueries({ queryKey: ['roster', classId] }); }, onError: (reason) => setError(reason.message) });
  function select(file?: File) { if (!file) return; const message = validateRosterFile(file); setError(message); if (!message) upload.mutate(file); }
  if (result) return <Dialog title="导入完成" onClose={onClose} footer={<button className="btn btn-primary" onClick={onClose}>完成</button>}><div className="import-result"><CheckCircle2 /><dl><div><dt>新增学生</dt><dd>{result.created_students}</dd></div><div><dt>新增名单</dt><dd>{result.created_enrollments}</dd></div><div><dt>恢复成员</dt><dd>{result.restored_enrollments}</dd></div><div><dt>跳过</dt><dd>{result.skipped}</dd></div></dl></div></Dialog>;
  return <Dialog title="导入学生名单" description={preview ? '检查校验结果并选择重复数据处理方式。' : '上传 CSV、XLS 或 XLSX 文件，最大 10 MiB。'} onClose={onClose} footer={preview ? <><button className="btn btn-secondary" onClick={() => setPreview(null)}>重新选择</button><button className="btn btn-primary" disabled={preview.summary.errors > 0 || confirm.isPending} onClick={() => confirm.mutate()}>确认导入</button></> : undefined}>
    {!preview ? <label className="file-drop"><FileSpreadsheet aria-hidden="true" /><strong>{upload.isPending ? '正在校验文件...' : '选择名单文件'}</strong><span>文件只用于本次解析，不会保存在浏览器中</span><input type="file" accept=".csv,.xls,.xlsx" disabled={upload.isPending} onChange={(e) => select(e.target.files?.[0])} /><span className="btn btn-secondary"><Upload />浏览文件</span></label> : <><div className="import-metrics"><span><strong>{preview.summary.total}</strong>总行数</span><span><strong>{preview.summary.valid}</strong>有效</span><span><strong>{preview.summary.errors}</strong>错误</span><span><strong>{preview.summary.duplicates}</strong>重复</span></div>{preview.summary.duplicates > 0 && <fieldset className="policy"><legend>重复学号处理</legend><label><input type="radio" checked={policy === 'skip'} onChange={() => setPolicy('skip')} /> 跳过已有成员</label><label><input type="radio" checked={policy === 'replace'} onChange={() => setPolicy('replace')} /> 恢复已移除关系</label></fieldset>}<div className="table-scroll"><table><thead><tr><th>行</th><th>学号</th><th>姓名</th><th>状态</th><th>说明</th></tr></thead><tbody>{preview.rows.map((row) => <tr key={row.row_number} className={row.status === 'error' ? 'error-row' : ''}><td>{row.row_number}</td><td>{row.student_number || '-'}</td><td>{row.name || '-'}</td><td>{previewStatusLabel(row.status)}</td><td>{row.message || '-'}</td></tr>)}</tbody></table></div></>}
    {error && <div className="form-alert" role="alert">{error}</div>}
  </Dialog>;
}
