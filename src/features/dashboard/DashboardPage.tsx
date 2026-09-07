import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowRight, BookOpen, CalendarDays, ClipboardCheck, Play } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useApi } from '../../app/auth';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { deriveDashboardMetrics } from './dashboard-selectors';

export function DashboardPage() {
  const api = useApi(); const navigate = useNavigate();
  const courses = useQuery({ queryKey: ['courses', 'dashboard'], queryFn: () => api.courses.list({ page_size: 100, status: 'ACTIVE' }) });
  const sessions = useQuery({ queryKey: ['sessions', 'dashboard'], queryFn: () => api.attendance.list({ page_size: 20 }) });
  const createSession = useMutation({ mutationFn: (classId: string) => api.attendance.create(classId, new Date().toLocaleDateString('en-CA')), onSuccess: (session) => navigate(`/attendance/${session.id}`) });
  if (courses.isLoading || sessions.isLoading) return <LoadingState label="正在加载工作台..." />;
  if (courses.error || sessions.error) return <ErrorState message={(courses.error || sessions.error as Error)?.message || '工作台加载失败'} retry={() => { void courses.refetch(); void sessions.refetch(); }} />;
  const courseItems = courses.data?.items ?? []; const sessionItems = sessions.data?.items ?? []; const metrics = deriveDashboardMetrics(courseItems, sessionItems);
  return <section className="page"><div className="page-header"><div><p className="eyebrow">今日教学</p><h1>工作台</h1><p>{new Intl.DateTimeFormat('zh-CN', { dateStyle: 'full' }).format(new Date())}</p></div><Link className="btn btn-secondary" to="/courses"><BookOpen />管理课程</Link></div>
    <div className="metrics-grid"><article className="metric"><BookOpen /><span>进行中课程</span><strong>{metrics.activeCourses} 门</strong></article><article className="metric"><CalendarDays /><span>活动班级</span><strong>{metrics.activeClasses} 个</strong></article><article className="metric"><ClipboardCheck /><span>近期到课率</span><strong>{metrics.attendanceRate}%</strong></article></div>
    <div className="dashboard-grid"><section className="panel"><header><div><h2>课程与班级</h2><p>从班级直接开始今天的点名</p></div></header>{courseItems.length ? <div className="list">{courseItems.flatMap((course) => course.classes.filter((item) => item.status === 'ACTIVE').map((item) => <article className="list-row" key={item.id}><div><strong>{course.name}</strong><p>{item.name} · {item.active_student_count} 人</p></div><button className="btn btn-primary" disabled={!item.active_student_count || createSession.isPending} onClick={() => createSession.mutate(item.id)}><Play />开始点名</button></article>))}</div> : <div className="inline-empty"><p>还没有课程</p><Link to="/courses">创建第一门课程 <ArrowRight /></Link></div>}</section>
      <section className="panel"><header><div><h2>最近场次</h2><p>{metrics.draftSessions} 个未完成场次</p></div></header><div className="list">{sessionItems.slice(0, 5).map((session) => <Link className="list-row" key={session.id} to={session.status === 'DRAFT' ? `/attendance/${session.id}` : `/records/${session.id}`}><div><strong>{session.course.name}</strong><p>{session.class_group.name} · {session.session_date}</p></div><span className={`status ${session.status.toLowerCase()}`}>{session.status === 'DRAFT' ? '进行中' : '已完成'}</span></Link>)}</div></section></div>
    {createSession.error && <div className="form-alert" role="alert">{createSession.error.message}</div>}
  </section>;
}
