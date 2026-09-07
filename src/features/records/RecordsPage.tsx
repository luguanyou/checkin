import { useQuery } from '@tanstack/react-query';
import { CalendarRange, Download, Filter } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { useApi } from '../../app/auth';
import { ErrorState, LoadingState, EmptyState } from '../../components/AsyncState';
import { Pagination } from '../../components/Pagination';

export function RecordsPage() {
  const api = useApi(); const [params, setParams] = useSearchParams(); const page = Number(params.get('page') || 1);
  const courseId = params.get('course_id') || ''; const classId = params.get('class_group_id') || ''; const status = params.get('status') || ''; const dateFrom = params.get('date_from') || ''; const dateTo = params.get('date_to') || '';
  const courses = useQuery({ queryKey: ['courses', 'record-filters'], queryFn: () => api.courses.list({ page_size: 100 }) });
  const query = useQuery({ queryKey: ['sessions', { page, courseId, classId, status, dateFrom, dateTo }], queryFn: () => api.attendance.list({ page, page_size: 20, course_id: courseId || undefined, class_group_id: classId || undefined, status: status || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }) });
  function update(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); if (key !== 'page') next.set('page', '1'); if (key === 'course_id') next.delete('class_group_id'); setParams(next); }
  if (query.isLoading) return <LoadingState label="正在加载考勤记录..." />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;
  const items = query.data?.items ?? []; const selectedCourse = courses.data?.items.find((course) => course.id === courseId);
  return <section className="page"><div className="page-header"><div><p className="eyebrow">数据追踪</p><h1>考勤记录</h1><p>按课程、班级和日期检索课堂点名结果。</p></div><span className="header-icon"><CalendarRange /></span></div>
    <div className="toolbar filters"><Filter /><label><span>课程</span><select value={courseId} onChange={(e) => update('course_id', e.target.value)}><option value="">全部课程</option>{courses.data?.items.map((course) => <option key={course.id} value={course.id}>{course.name}</option>)}</select></label><label><span>班级</span><select value={classId} onChange={(e) => update('class_group_id', e.target.value)}><option value="">全部班级</option>{selectedCourse?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>状态</span><select value={status} onChange={(e) => update('status', e.target.value)}><option value="">全部状态</option><option value="DRAFT">进行中</option><option value="COMPLETED">已完成</option></select></label><label><span>起始日期</span><input type="date" value={dateFrom} onChange={(e) => update('date_from', e.target.value)} /></label><label><span>结束日期</span><input type="date" value={dateTo} onChange={(e) => update('date_to', e.target.value)} /></label></div>
    {!items.length ? <EmptyState title="没有匹配的考勤场次" description="调整筛选条件后重试。" /> : <div className="panel table-scroll"><table><thead><tr><th>日期</th><th>课程</th><th>班级</th><th>进度</th><th>异常</th><th>状态</th><th>操作</th></tr></thead><tbody>{items.map((session) => <tr key={session.id}><td className="mono">{session.session_date}</td><td><strong>{session.course.name}</strong><small>{session.course.code}</small></td><td>{session.class_group.name}</td><td>{session.summary.total - session.summary.pending}/{session.summary.total}</td><td>{session.summary.exceptions}</td><td><span className={`status ${session.status.toLowerCase()}`}>{session.status === 'DRAFT' ? '进行中' : '已完成'}</span></td><td><div className="actions"><Link className="btn btn-secondary btn-sm" to={session.status === 'DRAFT' ? `/attendance/${session.id}` : `/records/${session.id}`}>{session.status === 'DRAFT' ? '继续点名' : '查看详情'}</Link>{session.status === 'COMPLETED' && <Link className="icon-btn" to={`/records/${session.id}`} aria-label="导出"><Download /></Link>}</div></td></tr>)}</tbody></table></div>}
    <Pagination page={page} pageSize={query.data?.page_size ?? 20} total={query.data?.total ?? 0} onChange={(value) => update('page', String(value))} />
  </section>;
}
