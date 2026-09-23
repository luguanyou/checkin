import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useApi } from '../../app/auth';
import type { Course } from '../../api/types';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { ScoreEditor } from './ScoreEditor';
import { discardMessage, useUnsavedScores } from './useUnsavedScores';
import './scores.css';

export function ScoresPage() {
  const api = useApi(); const queryClient = useQueryClient(); const [params, setParams] = useSearchParams();
  const [dirty, setDirty] = useState(false); const releaseGuard = useUnsavedScores(dirty);
  const [initialSelection, setInitialSelection] = useState<{ courseId: string; classId: string } | null>(null);
  const context = useQuery({ queryKey: ['courses', 'scores-context'], queryFn: async () => {
    const all: Course[] = []; let page = 1;
    do { const result = await api.courses.list({ page, page_size: 100 }); all.push(...result.items); if (all.length >= result.total || !result.items.length) break; page++; } while (true);
    return all;
  } });
  const courses = context.data ?? [];
  useEffect(() => {
    if (!initialSelection && courses.length) {
      const initialCourse = courses.find((item) => item.id === params.get('course_id')) ?? courses[0];
      setInitialSelection({ courseId: initialCourse.id, classId: initialCourse.classes[0]?.id ?? '' });
    }
  }, [courses, initialSelection, params]);
  const requestedClass = params.get('class_group_id');
  const classCourse = courses.find((course) => course.classes.some((item) => item.id === requestedClass));
  const courseId = classCourse?.id || params.get('course_id') || initialSelection?.courseId || courses[0]?.id || '';
  const course = courses.find((item) => item.id === courseId);
  const classId = requestedClass ?? (initialSelection?.courseId === courseId ? initialSelection.classId : course?.classes[0]?.id ?? '');
  const query = useQuery({ queryKey: ['scores', classId], queryFn: () => api.scores.get(classId), enabled: Boolean(classId), refetchOnWindowFocus: false });
  const displayedCourseId = query.data?.course.id ?? (requestedClass && !classCourse ? '' : courseId);
  const displayedCourse = courses.find((row) => row.id === displayedCourseId);
  useEffect(() => { setDirty(false); }, [classId]);
  function choose(nextCourse: string, nextClass: string) {
    if (dirty && !window.confirm(discardMessage)) return;
    releaseGuard(); setDirty(false); setParams({ course_id: nextCourse, ...(nextClass ? { class_group_id: nextClass } : {}) });
  }
  return <section className="page scores-page">
    <div className="page-header"><div><p className="eyebrow">教学评价</p><h1>平时成绩</h1><p>基础分 + 各类别净积分 × 换算系数；各班独立配置。</p></div><span className="status active">基础分＋表现积分</span></div>
    {context.isLoading ? <LoadingState label="正在加载课程班级..." /> : context.error && !context.data ? <ErrorState message={context.error.message} retry={() => void context.refetch()} /> : <>
      {context.error && <div className="form-alert" role="alert">课程列表刷新失败，保留当前班级和输入。<button className="btn btn-secondary" onClick={() => void context.refetch()}>重试加载课程</button></div>}
      <div className="toolbar scores-context"><label className="field"><span>课程</span><select value={displayedCourseId} onChange={(e) => choose(e.target.value, courses.find((item) => item.id === e.target.value)?.classes[0]?.id ?? '')}>{!displayedCourse && <option value={displayedCourseId}>{query.data?.course.name ?? '请选择课程'}</option>}{courses.map((item) => <option value={item.id} key={item.id}>{item.name}{item.status === 'ARCHIVED' ? '（已归档）' : ''}</option>)}</select></label><label className="field"><span>班级</span><select value={classId} onChange={(e) => choose(displayedCourseId, e.target.value)}>{!displayedCourse?.classes.some((row) => row.id === classId) && <option value={classId}>{query.data?.class_group.name ?? '请选择班级'}</option>}{displayedCourse?.classes.map((item) => <option value={item.id} key={item.id}>{item.name}{item.status === 'ARCHIVED' ? '（已归档）' : ''}</option>)}</select></label></div>
      {query.error && query.data && <div className="form-alert" role="alert">成绩刷新失败，已保留当前输入。<button className="btn btn-secondary" onClick={() => void query.refetch()}>重试加载成绩</button></div>}
      {!classId ? <EmptyState title="还没有可用班级" description="请先在课程班级页面创建课程和班级。" /> : query.isLoading ? <LoadingState label="正在加载平时成绩..." /> : query.error && !query.data ? <ErrorState message={query.error.message} retry={() => void query.refetch()} /> : query.data && <ScoreEditor key={classId} book={query.data} onDirty={setDirty} onBook={(book) => queryClient.setQueryData(['scores', classId], book)} />}
    </>}
  </section>;
}
