import { useQuery } from '@tanstack/react-query';
import { useApi, useAuth } from '../../app/auth';
import { ErrorState, LoadingState } from '../../components/AsyncState';
import { ContentList } from './ContentList';

export function StudentTeachingContent({ classId }: { classId: string }) {
  const api = useApi();
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ['student-teaching-content', user?.id, classId],
    queryFn: () => api.teachingContent.studentList(classId),
    refetchInterval: 15000,
    gcTime: 0,
  });
  if (query.isPending) return <LoadingState label="正在加载课程资料和作业…" />;
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.refetch()} />;

  return <>
    <section className="panel teaching-panel">
      <header><h2>作业</h2></header>
      <ContentList classId={classId} items={query.data.items} kind="ASSIGNMENT" student />
    </section>
    <section className="panel teaching-panel">
      <header><h2>课程资料</h2></header>
      <ContentList classId={classId} items={query.data.items} kind="MATERIAL" student />
    </section>
  </>;
}
