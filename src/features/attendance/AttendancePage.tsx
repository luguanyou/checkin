import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Check, ChevronLeft, CircleAlert, Clock3, LogOut, Megaphone, MicOff, RefreshCw, UserX, Volume2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import type { AttendanceRecord, AttendanceStatus } from '../../api/types';
import { useApi } from '../../app/auth';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { Dialog } from '../../components/Dialog';
import { useSpeech } from '../../hooks/useSpeech';
import { attendanceActionForKey, canCompleteSession, clampIndex, exceptionRecords, firstPendingIndex, summarizeRecords } from './attendance-state';

const controls: { status: Exclude<AttendanceStatus, 'pending'>; label: string; key: string; icon: typeof Check }[] = [
  { status: 'present', label: '已到', key: 'Space', icon: Check }, { status: 'absent', label: '缺勤', key: '1', icon: UserX },
  { status: 'leave', label: '请假', key: '2', icon: CircleAlert }, { status: 'late', label: '迟到', key: '3', icon: Clock3 },
];

export function AttendancePage() {
  const { sessionId = '' } = useParams(); const api = useApi(); const navigate = useNavigate(); const queryClient = useQueryClient(); const speech = useSpeech({
    // 服务器 TTS 音频兜底：Chrome（国内拉不到 Google 语音包）等环境系统语音无声时自动改播 MP3
    audioFallback: (text, rate) => api.tts.speak(text, rate),
  });
  const query = useQuery({ queryKey: ['session', sessionId], queryFn: () => api.attendance.get(sessionId) });
  const [records, setRecords] = useState<AttendanceRecord[]>([]); const recordsRef = useRef(records); const [index, setIndex] = useState(0);
  const [pending, setPending] = useState(0); const [failed, setFailed] = useState(0); const [error, setError] = useState(''); const [showEnd, setShowEnd] = useState(false); const [completing, setCompleting] = useState(false);
  const queues = useRef(new Map<string, Promise<void>>());
  useEffect(() => { if (query.data) { setRecords(query.data.records); recordsRef.current = query.data.records; setIndex(firstPendingIndex(query.data.records)); } }, [query.data]);
  useEffect(() => { recordsRef.current = records; }, [records]);
  const speakNext = useCallback((nextIndex: number) => {
    const next = recordsRef.current[nextIndex];
    if (next) speech.speak(next.student_name);
  }, [speech]);
  const moveNext = useCallback(() => {
    const nextIndex = clampIndex(index + 1, recordsRef.current.length);
    setIndex(nextIndex);
    speakNext(nextIndex);
  }, [index, speakNext]);
  const mark = useCallback((status: Exclude<AttendanceStatus, 'pending'>) => {
    const target = recordsRef.current[index]; if (!target || query.data?.status !== 'DRAFT') return;
    const previousStatus = target.status; const mutationId = crypto.randomUUID();
    setRecords((items) => items.map((item) => item.id === target.id ? { ...item, status } : item));
    const nextIndex = clampIndex(index + 1, recordsRef.current.length);
    setIndex(nextIndex); if (nextIndex !== index) speakNext(nextIndex); setPending((value) => value + 1); setError('');
    const before = queues.current.get(target.id) ?? Promise.resolve();
    const task = before.catch(() => undefined).then(async () => {
      const latest = recordsRef.current.find((item) => item.id === target.id) ?? target;
      const updated = await api.attendance.updateRecord(target.id, { status, expected_version: latest.version, client_mutation_id: mutationId });
      setRecords((items) => items.map((item) => item.id === updated.id ? updated : item));
    }).catch((reason: unknown) => {
      setFailed((value) => value + 1);
      setRecords((items) => items.map((item) => item.id === target.id ? { ...item, status: previousStatus } : item));
      if (reason instanceof ApiError && reason.code === 'ATTENDANCE_RECORD_CONFLICT') void query.refetch();
      setError(reason instanceof Error ? reason.message : '考勤状态保存失败');
    }).finally(() => { setPending((value) => Math.max(0, value - 1)); queues.current.delete(target.id); });
    queues.current.set(target.id, task);
  }, [api.attendance, index, query, speakNext]);
  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      const editable = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement;
      const action = attendanceActionForKey(event.key, editable); if (!action) return; event.preventDefault();
      if (action === 'previous') setIndex((value) => clampIndex(value - 1, recordsRef.current.length));
      else if (action === 'repeat') { const current = recordsRef.current[index]; if (current) speech.speak(current.student_name); }
      else if (action === 'mute') speech.toggleMuted(); else mark(action);
    }
    window.addEventListener('keydown', keydown); return () => window.removeEventListener('keydown', keydown);
  }, [index, mark, speech]);
  async function complete() { setCompleting(true); try { const completed = await api.attendance.complete(sessionId); queryClient.setQueryData(['session', sessionId], { ...completed, records }); await queryClient.invalidateQueries({ queryKey: ['sessions'] }); navigate(`/records/${sessionId}`); } catch (reason) { setError((reason as Error).message); } finally { setCompleting(false); } }
  if (query.isLoading) return <LoadingState label="正在载入点名场次..." />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;
  if (!query.data || !records.length) return <ErrorState message="这个场次没有可点名的学生" />;
  if (query.data.status === 'COMPLETED') return <main className="attendance-page"><ErrorState message="该场次已经完成，不能继续点名。" /><Link className="btn btn-secondary" to={`/records/${sessionId}`}>查看场次详情</Link></main>;
  const current = records[index]; const summary = summarizeRecords(records); const exceptions = exceptionRecords(records); const mayComplete = canCompleteSession(records, pending, failed);
  return <main className="attendance-page"><header className="attendance-topbar"><Link className="btn btn-ghost" to="/"><ArrowLeft />返回工作台</Link><div><strong>{query.data.course.name}</strong><span>{query.data.class_group.name} · {query.data.session_date}</span></div><div className="attendance-top-actions"><span className={`sync ${error ? 'error' : pending ? 'syncing' : 'synced'}`}>{error ? '保存失败' : pending ? `${pending} 项同步中` : '全部已同步'}</span><button className="btn btn-primary" onClick={() => setShowEnd(true)}><LogOut />结束点名</button></div></header>
    <div className="attendance-layout"><section className="rollcall-main"><div className="progress-line"><span>进度 {summary.processed} / {summary.total}</span><span>{summary.attendanceRate}% 到课</span></div><div className="progress"><span style={{ width: `${summary.total ? summary.processed / summary.total * 100 : 0}%` }} /></div><article className={`student-focus ${current.status}`}><span className="student-index">当前学生 · {index + 1}</span><h1>{current.student_name}</h1><p>{current.student_number} · {current.class_name}</p><span className={`status ${current.status}`}>{statusLabel(current.status)}</span></article><div className="attendance-controls">{controls.map(({ status, label, key, icon: Icon }) => <button key={status} className={`attendance-button ${status}`} onClick={() => mark(status)}><Icon /><strong>{label}</strong><kbd>{key}</kbd></button>)}</div><div className="utility-controls"><button className="btn btn-secondary" onClick={() => setIndex((value) => clampIndex(value - 1, records.length))}><ChevronLeft />上一位</button><button className="btn btn-secondary" onClick={moveNext} disabled={index >= records.length - 1}><ChevronLeft className="rotate-180" />下一位</button><button className="btn btn-secondary" onClick={() => speech.speak(current.student_name)} disabled={speech.muted}><Megaphone />重新播报</button><button className="btn btn-secondary" onClick={speech.toggleMuted}>{speech.muted ? <Volume2 /> : <MicOff />}{speech.muted ? '开启语音' : '静音'}</button></div><div className="speech-settings" aria-label="语音设置"><label>语速 <input aria-label="语速" type="range" min="0.5" max="2" step="0.1" value={speech.rate} onChange={(event) => speech.setRate(Number(event.target.value))} /><output>{speech.rate.toFixed(1)}x</output></label><label>音色 <select aria-label="音色" value={speech.voiceName} onChange={(event) => speech.setVoice(event.target.value)} disabled={!speech.supported || !speech.voices.length}><option value="">系统默认</option>{speech.voices.map((voice) => <option key={voice.voiceURI || voice.name} value={voice.voiceURI || voice.name}>{voice.name} ({voice.lang})</option>)}</select></label></div>{!speech.supported && <p className="speech-note">当前浏览器不支持语音播报，手动点名不受影响。</p>}{speech.error && <p className="speech-note speech-error" role="alert">{speech.error}</p>}{error && <div className="form-alert" role="alert">{error} <button onClick={() => { setFailed(0); void query.refetch(); }}><RefreshCw />重新载入</button></div>}</section>
      <aside className="exception-panel"><header><div><h2>异常名单</h2><p>缺勤和迟到共 {exceptions.length} 人</p></div></header>{exceptions.length ? <div className="list">{exceptions.map((item) => <div className="list-row" key={item.id}><div><strong>{item.student_name}</strong><p>{item.student_number}</p></div><span className={`status ${item.status}`}>{statusLabel(item.status)}</span></div>)}</div> : <div className="inline-empty"><Check /><p>暂无异常记录</p></div>}</aside></div>
    {showEnd && <Dialog title="结束本次点名" description="提交后场次将不可恢复为草稿。" onClose={() => setShowEnd(false)} footer={<><button className="btn btn-secondary" onClick={() => setShowEnd(false)}>取消</button><button className="btn btn-primary" disabled={!mayComplete || completing} onClick={() => void complete()}>确认结束</button></>}><div className="end-summary"><p>已确认 {summary.processed} 人，待确认 {summary.pending} 人。</p>{!mayComplete && <div className="form-alert">请确保所有变更同步成功后再结束点名。</div>}</div></Dialog>}
  </main>;
}

function statusLabel(status: AttendanceStatus) { return ({ pending: '待确认', present: '已到', absent: '缺勤', leave: '请假', late: '迟到' } as Record<AttendanceStatus, string>)[status]; }
