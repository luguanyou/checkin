import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ContentKind, TeacherTeachingContent } from '../../api/teaching-content-types';
import { useApi } from '../../app/auth';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { Dialog } from '../../components/Dialog';
import { useToast } from '../../components/ToastProvider';
import { ContentForm } from './ContentForm';
import { ContentList } from './ContentList';

export function TeachingContentPage() {
  const { classId = '' } = useParams();
  return <TeachingContentEditor key={classId} classId={classId} />;
}

function TeachingContentEditor({ classId }: { classId: string }) {
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<{ kind: ContentKind; item?: TeacherTeachingContent } | null>(null);
  const [withdrawing, setWithdrawing] = useState<TeacherTeachingContent | null>(null);
  const query = useQuery({ queryKey: ['teaching-content', classId], queryFn: () => api.teachingContent.list(classId) });
  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['teaching-content'] });
    void queryClient.invalidateQueries({ queryKey: ['student-teaching-content'] });
  }
  const withdraw = useMutation({
    mutationFn: (id: string) => api.teachingContent.withdraw(classId, id),
    onSuccess: () => { setWithdrawing(null); refresh(); toast.show('已撤回'); },
  });
  const data = query.data;
  const classes = data?.classes ?? [];
  const currentClass = classes.find((group) => group.id === classId);
  function actions(item: TeacherTeachingContent) {
    return <>
      <p className="muted">发布班级：{classes.filter((group) => item.class_ids.includes(group.id)).map((group) => group.name).join('、')}</p>
      <div className="actions">
        <button className="btn btn-ghost btn-sm" onClick={() => setEditing({ kind: item.kind, item })}>编辑</button>
        <button className="btn btn-ghost btn-sm" onClick={() => { withdraw.reset(); setWithdrawing(item); }}>撤回</button>
      </div>
    </>;
  }
  return <section className="page">
    <header className="page-header">
      <div><p className="eyebrow">课程班级</p><h1>教学内容</h1>
        {data && <p>{data.course_name} · {currentClass?.name}</p>}
      </div>
      <Link className="btn btn-secondary" to="/courses">返回课程班级</Link>
    </header>
    {query.isPending ? <LoadingState /> : query.error ? <ErrorState message={query.error.message} retry={() => void query.refetch()} /> : data && <>
      <section className="panel teaching-panel">
        <header><h2>作业</h2><button className="btn btn-primary btn-sm" onClick={() => setEditing({ kind: 'ASSIGNMENT' })}>布置作业</button></header>
        <ContentList classId={classId} items={data.items} kind="ASSIGNMENT" actions={actions} />
      </section>
      <section className="panel teaching-panel">
        <header><h2>课程资料</h2><button className="btn btn-primary btn-sm" onClick={() => setEditing({ kind: 'MATERIAL' })}>发布资料</button></header>
        <ContentList classId={classId} items={data.items} kind="MATERIAL" actions={actions} />
      </section>
      {editing && <ContentForm classId={classId} classes={classes} kind={editing.kind} initial={editing.item}
        materials={data.items.filter((item) => item.kind === 'MATERIAL')} onClose={() => setEditing(null)}
        onSaved={() => { toast.show(editing.item ? '修改已保存' : '发布成功'); setEditing(null); refresh(); }} />}
    </>}
    {withdrawing && <Dialog title="撤回教学内容" onClose={() => { if (!withdraw.isPending) setWithdrawing(null); }}
      footer={<>
        <button className="btn btn-secondary" disabled={withdraw.isPending} onClick={() => setWithdrawing(null)}>取消</button>
        <button className="btn btn-danger" disabled={withdraw.isPending} onClick={() => withdraw.mutate(withdrawing.id)}>确认撤回</button>
      </>}>
      <p>撤回「{withdrawing.title}」后，所有接收班级将无法在系统中查看该内容。</p>
      {withdrawing.class_ids.length > 1 && <p>如需仅从个别班级撤回，请编辑发布班级。</p>}
      {withdraw.error && <p className="form-alert" role="alert">{withdraw.error.message}</p>}
    </Dialog>}
  </section>;
}
