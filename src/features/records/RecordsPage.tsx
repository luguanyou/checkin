import { useQuery } from '@tanstack/react-query';
import { CalendarRange, Download, Filter } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { useState } from 'react';
import { useApi } from '../../app/auth';
import { ErrorState, LoadingState, EmptyState } from '../../components/AsyncState';
import { Pagination } from '../../components/Pagination';
import { Dialog } from '../../components/Dialog';
import { useToast } from '../../components/ToastProvider';

export function RecordsPage() {
  const api = useApi(); const [params, setParams] = useSearchParams(); const page = Number(params.get('page') || 1);
  const toast = useToast();
  const [exportMode, setExportMode] = useState<'course' | 'template' | 'scores' | null>(null);
  const [exporting, setExporting] = useState(false);
  const courseId = params.get('course_id') || ''; const classId = params.get('class_group_id') || ''; const status = params.get('status') || ''; const dateFrom = params.get('date_from') || ''; const dateTo = params.get('date_to') || '';
  const courses = useQuery({ queryKey: ['courses', 'record-filters'], queryFn: () => api.courses.list({ page_size: 100 }) });
  const query = useQuery({ queryKey: ['sessions', { page, courseId, classId, status, dateFrom, dateTo }], queryFn: () => api.attendance.list({ page, page_size: 20, course_id: courseId || undefined, class_group_id: classId || undefined, status: status || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }) });
  function update(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); if (key !== 'page') next.set('page', '1'); if (key === 'course_id') next.delete('class_group_id'); setParams(next); }
  if (query.isLoading) return <LoadingState label="正在加载考勤记录..." />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;
  const items = query.data?.items ?? []; const selectedCourse = courses.data?.items.find((course) => course.id === courseId);
  async function exportCourse() {
    if (!courseId || exporting) return;
    setExporting(true);
    try {
      const file = exportMode === 'scores'
        ? await api.attendance.exportScores(courseId, classId || undefined)
        : exportMode === 'template'
        ? await api.attendance.exportTemplate(courseId, classId || undefined)
        : await api.attendance.exportCourse(courseId, classId || undefined);
      const url = URL.createObjectURL(file.blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = file.filename; anchor.click();
      URL.revokeObjectURL(url);
      setExportMode(null); toast.show(exportMode === 'scores' ? '平时分已生成' : exportMode === 'template' ? '模板考勤与平时成绩已生成' : '课程考勤汇总已生成');
    } catch (reason) { toast.show((reason as Error).message, 'error'); }
    finally { setExporting(false); }
  }
  return <section className="page"><div className="page-header"><div><p className="eyebrow">数据追踪</p><h1>考勤记录</h1><p>按课程、班级和日期检索课堂点名结果。</p></div><span className="header-icon"><CalendarRange /></span></div>
    <div className="toolbar filters"><Filter /><label><span>课程</span><select value={courseId} onChange={(e) => update('course_id', e.target.value)}><option value="">全部课程</option>{courses.data?.items.map((course) => <option key={course.id} value={course.id}>{course.name}</option>)}</select></label><label><span>班级</span><select value={classId} onChange={(e) => update('class_group_id', e.target.value)}><option value="">全部班级</option>{selectedCourse?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>状态</span><select value={status} onChange={(e) => update('status', e.target.value)}><option value="">全部状态</option><option value="DRAFT">进行中</option><option value="COMPLETED">已完成</option></select></label><label><span>起始日期</span><input type="date" value={dateFrom} onChange={(e) => update('date_from', e.target.value)} /></label><label><span>结束日期</span><input type="date" value={dateTo} onChange={(e) => update('date_to', e.target.value)} /></label></div>
    <div className="toolbar"><button className="btn btn-primary" disabled={!courseId} onClick={() => setExportMode('course')}><Download />导出课程考勤</button><button className="btn btn-secondary" disabled={!courseId} onClick={() => setExportMode('template')}><Download />按模板导出（含平时分）</button><button className="btn btn-secondary" disabled={!courseId} onClick={() => setExportMode('scores')}><Download />导出平时分</button><span>{courseId ? '汇总所选课程全部已完成场次，可按班级导出。' : '请先选择一门课程，再导出全部上课记录。'}</span></div>
    {!items.length ? <EmptyState title="没有匹配的考勤场次" description="调整筛选条件后重试。" /> : <div className="panel table-scroll"><table><thead><tr><th>日期</th><th>课程</th><th>班级</th><th>进度</th><th>异常</th><th>状态</th><th>操作</th></tr></thead><tbody>{items.map((session) => <tr key={session.id}><td className="mono">{session.session_date}</td><td><strong>{session.course.name}</strong><small>{session.course.code}</small></td><td>{session.class_group.name}</td><td>{session.summary.total - session.summary.pending}/{session.summary.total}</td><td>{session.summary.exceptions}</td><td><span className={`status ${session.status.toLowerCase()}`}>{session.status === 'DRAFT' ? '进行中' : '已完成'}</span></td><td><div className="actions"><Link className="btn btn-secondary btn-sm" to={session.status === 'DRAFT' ? `/attendance/${session.id}` : `/records/${session.id}`}>{session.status === 'DRAFT' ? '继续点名' : '查看详情'}</Link>{session.status === 'COMPLETED' && <Link className="icon-btn" to={`/records/${session.id}`} aria-label="导出"><Download /></Link>}</div></td></tr>)}</tbody></table></div>}
    <Pagination page={page} pageSize={query.data?.page_size ?? 20} total={query.data?.total ?? 0} onChange={(value) => update('page', String(value))} />
    {exportMode && <Dialog title={exportMode === 'scores' ? '导出平时分' : exportMode === 'template' ? '按原模板导出考勤与平时分' : '导出课程考勤汇总'} description={`${selectedCourse?.name || '所选课程'} · ${selectedCourse?.classes.find((item) => item.id === classId)?.name || '全部班级'}`} onClose={() => { if (!exporting) setExportMode(null); }} footer={<><button className="btn btn-secondary" disabled={exporting} onClick={() => setExportMode(null)}>取消</button><button className="btn btn-primary" disabled={exporting} onClick={() => void exportCourse()}>{exporting ? '正在生成…' : '生成 Excel'}</button></>}><p>{exportMode === 'scores' ? '导出所选课程、班级的全部学生平时分，不受考勤日期、状态和分页影响。' : '导出所选课程、班级全部已完成场次，不受列表日期、状态和分页影响。'}</p>{exportMode === 'scores' ? <p>导出每位学生的百分制平时分、名单状态及评价状态，每班一张工作表。成绩沿用系统基础分和全部类别系数；未评项目按系统规则暂计 0 分。规则未配置时会提示先配置。</p> : exportMode === 'template' ? <><p>保留原 Excel 的合并单元格、行列尺寸和打印版式，填入考勤、课堂表现、作业及平时成绩。超出 25 次考勤、6 个同类项目或 41 名学生时自动生成同版式续表。</p><p>平时分沿用“平时成绩”已配置的基础分和全部类别系数，填百分制成绩；未评项目按系统规则暂计 0 分，规则未配置时会提示。期末成绩和总分留空。</p></> : <p>每个班级一张工作表，每名学生一行，每次课一列；同一天多次课分别列出。保留历史学生，缺少考勤记录时留空。</p>}</Dialog>}
  </section>;
}
