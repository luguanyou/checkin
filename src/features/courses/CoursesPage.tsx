import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, BookOpen, Pencil, Plus, Trash2, UsersRound } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useApi } from '../../app/auth';
import type { ClassGroup, Course } from '../../api/types';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { Dialog } from '../../components/Dialog';
import { Pagination } from '../../components/Pagination';
import { useToast } from '../../components/ToastProvider';

type DialogKind = 'course-create' | 'course-edit' | 'class-create' | 'class-edit';

export function CoursesPage() {
  const api = useApi();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page') || 1);
  const q = params.get('q') || '';
  const status = params.get('status') || 'ACTIVE';
  const [dialog, setDialog] = useState<DialogKind | null>(null);
  const [selectedCourse, setSelectedCourse] = useState<Course | null>(null);
  const [selectedClass, setSelectedClass] = useState<ClassGroup | null>(null);
  const query = useQuery({ queryKey: ['courses', { page, q, status }], queryFn: () => api.courses.list({ page, page_size: 20, q: q || undefined, status }) });
  const archive = useMutation({ mutationFn: (course: Course) => api.courses.update(course.id, { status: course.status === 'ACTIVE' ? 'ARCHIVED' : 'ACTIVE' }), onSuccess: () => { toast.show('课程状态已更新'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }, onError: (reason) => toast.show((reason as Error).message) });
  const deleteCourse = useMutation({ mutationFn: (course: Course) => api.courses.delete(course.id), onSuccess: () => { toast.show('课程已删除'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }, onError: (reason) => toast.show((reason as Error).message) });
  const deleteClass = useMutation({ mutationFn: (item: ClassGroup) => api.courses.deleteClass(item.id, true), onSuccess: () => { toast.show('班级及关联数据已删除'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }, onError: (reason) => toast.show((reason as Error).message) });
  function update(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); if (key !== 'page') next.set('page', '1'); setParams(next); }
  function confirmDeleteCourse(course: Course) { if (window.confirm(`确定删除课程“${course.name}”吗？删除后不可恢复。`)) deleteCourse.mutate(course); }
  function confirmDeleteClass(item: ClassGroup) { if (window.confirm(`确定删除班级“${item.name}”吗？该班级的学生名单和全部历史考勤记录将永久删除，且无法恢复。`)) deleteClass.mutate(item); }
  if (query.isLoading) return <LoadingState label="正在加载课程..." />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;
  const items = query.data?.items ?? [];
  return <section className="page"><div className="page-header"><div><p className="eyebrow">教学资源</p><h1>课程班级</h1><p>维护课程与用于点名的教学班级。</p></div><button className="btn btn-primary" onClick={() => setDialog('course-create')}><Plus />新建课程</button></div>
    <div className="toolbar"><label className="search-field"><span className="sr-only">搜索课程</span><input placeholder="搜索课程名称或代码" value={q} onChange={(e) => update('q', e.target.value)} /></label><label><span className="sr-only">课程状态</span><select value={status} onChange={(e) => update('status', e.target.value)}><option value="ACTIVE">进行中</option><option value="ARCHIVED">已归档</option></select></label></div>
    {!items.length ? <EmptyState title="没有匹配的课程" description="调整筛选条件或新建一门课程。" action={<button className="btn btn-primary" onClick={() => setDialog('course-create')}><Plus />新建课程</button>} /> : <div className="course-grid">{items.map((course) => <article className="course-card" key={course.id}><header><span className="course-icon"><BookOpen /></span><div><h2>{course.name}</h2><p>{course.code} · {course.term}</p></div><span className={`status ${course.status.toLowerCase()}`}>{course.status === 'ACTIVE' ? '进行中' : '已归档'}</span></header><div className="class-list">{course.classes.length ? course.classes.map((item) => <div className="class-row" key={item.id}><div><strong>{item.name}</strong><p><UsersRound />{item.active_student_count} 名学生</p></div><div className="actions"><Link className="btn btn-secondary" to={`/classes/${item.id}/roster`}>管理名单</Link><button className="btn btn-ghost btn-sm" aria-label={`编辑班级 ${item.name}`} title="编辑班级" onClick={() => { setSelectedCourse(course); setSelectedClass(item); setDialog('class-edit'); }}><Pencil />编辑</button><button className="btn btn-ghost btn-sm" aria-label={`删除班级 ${item.name}`} title="删除班级" onClick={() => confirmDeleteClass(item)} disabled={deleteClass.isPending}><Trash2 />删除</button></div></div>) : <p className="muted">尚未创建班级</p>}</div><footer><button className="btn btn-ghost" onClick={() => { setSelectedCourse(course); setDialog('class-create'); }}><Plus />新建班级</button><div className="actions"><button className="btn btn-ghost" aria-label="编辑课程" onClick={() => { setSelectedCourse(course); setDialog('course-edit'); }}><Pencil />编辑课程</button><button className="btn btn-ghost" aria-label="删除课程" onClick={() => confirmDeleteCourse(course)} disabled={deleteCourse.isPending}><Trash2 />删除课程</button><button className="btn btn-ghost" onClick={() => archive.mutate(course)} disabled={archive.isPending}><Archive />{course.status === 'ACTIVE' ? '归档课程' : '恢复课程'}</button></div></footer></article>)}</div>}
    <Pagination page={page} pageSize={query.data?.page_size ?? 20} total={query.data?.total ?? 0} onChange={(value) => update('page', String(value))} />
    {dialog === 'course-create' && <CourseForm api={api} close={() => setDialog(null)} done={() => { setDialog(null); toast.show('课程已创建'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }} />}
    {dialog === 'course-edit' && selectedCourse && <CourseForm api={api} initial={selectedCourse} close={() => setDialog(null)} done={() => { setDialog(null); toast.show('课程名称已更新'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }} />}
    {dialog === 'class-create' && selectedCourse && <ClassForm course={selectedCourse} api={api} close={() => setDialog(null)} done={() => { setDialog(null); toast.show('班级已创建'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }} />}
    {dialog === 'class-edit' && selectedCourse && selectedClass && <ClassForm course={selectedCourse} api={api} initial={selectedClass} close={() => setDialog(null)} done={() => { setDialog(null); toast.show('班级名称已更新'); void queryClient.invalidateQueries({ queryKey: ['courses'] }); }} />}
  </section>;
}

function CourseForm({ api, initial, close, done }: { api: ReturnType<typeof useApi>; initial?: Course; close(): void; done(): void }) {
  const editing = Boolean(initial);
  const [name, setName] = useState(initial?.name ?? ''); const [code, setCode] = useState(initial?.code ?? ''); const [term, setTerm] = useState(initial?.term ?? '2026 秋季学期'); const [error, setError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); if (!name.trim() || (!editing && (!code.trim() || !term.trim()))) return setError(editing ? '请输入课程名称' : '请完整填写课程名称、代码和学期'); setPending(true); setError(''); try { if (initial) await api.courses.update(initial.id, { name: name.trim() }); else await api.courses.create({ name: name.trim(), code: code.trim(), term: term.trim() }); done(); } catch (reason) { setError((reason as Error).message); } finally { setPending(false); } }
  return <Dialog title={editing ? '编辑课程' : '新建课程'} description={editing ? '修改课程名称。' : '创建后可继续添加教学班级。'} onClose={close} footer={<><button className="btn btn-secondary" onClick={close}>取消</button><button className="btn btn-primary" form="course-form" disabled={pending}>{editing ? '保存课程' : '创建课程'}</button></>}><form id="course-form" onSubmit={submit}><label className="field"><span>课程名称</span><input autoFocus value={name} onChange={(e) => setName(e.target.value)} /></label>{!editing && <><label className="field"><span>课程代码</span><input value={code} onChange={(e) => setCode(e.target.value)} /></label><label className="field"><span>学期</span><input value={term} onChange={(e) => setTerm(e.target.value)} /></label></>}{error && <div className="form-alert">{error}</div>}</form></Dialog>;
}

function ClassForm({ course, api, initial, close, done }: { course: Course; api: ReturnType<typeof useApi>; initial?: ClassGroup; close(): void; done(): void }) {
  const editing = Boolean(initial);
  const [name, setName] = useState(initial?.name ?? ''); const [error, setError] = useState(''); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); if (!name.trim()) return setError('请输入班级名称'); setPending(true); setError(''); try { if (initial) await api.courses.updateClass(initial.id, { name: name.trim() }); else await api.courses.createClass(course.id, name.trim()); done(); } catch (reason) { setError((reason as Error).message); } finally { setPending(false); } }
  return <Dialog title={editing ? '编辑班级' : '新建班级'} description={course.name} onClose={close} footer={<><button className="btn btn-secondary" onClick={close}>取消</button><button className="btn btn-primary" form="class-form" disabled={pending}>{editing ? '保存班级' : '创建班级'}</button></>}><form id="class-form" onSubmit={submit}><label className="field"><span>班级名称</span><input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：2024 级 2 班" /></label>{error && <div className="form-alert">{error}</div>}</form></Dialog>;
}
