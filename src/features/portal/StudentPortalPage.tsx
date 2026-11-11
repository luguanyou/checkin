import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi, useAuth } from '../../app/auth';
import { EmptyState, ErrorState, LoadingState } from '../../components/AsyncState';
import { categories, displayPoints, displayScore } from '../scores/score-utils';
import { StudentTeachingContent } from '../teaching-content/StudentTeachingContent';

const attendanceLabels: Record<string, string> = { pending: '待点名', present: '出勤', absent: '缺勤', leave: '请假', late: '迟到' };

export function StudentPortalPage() {
  const api = useApi(); const { user, logout } = useAuth();
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const classes = useQuery({ queryKey: ['student-classes', user?.id], queryFn: () => api.portal.classes(), refetchInterval: 15000 });
  const selectedClass = classes.data?.items.find((item) => item.id === params.get('class'));
  const classId = selectedClass?.id ?? '';
  const detail = useQuery({ queryKey: ['student-class', user?.id, classId], queryFn: () => api.portal.get(classId), enabled: Boolean(classId), refetchInterval: 15000, gcTime: 0 });
  const data = detail.data;
  return <main className="page" style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
    <header className="page-header"><div><p className="eyebrow">学生个人中心</p><h1>我的课程</h1><p>{user?.display_name} · {user?.username}</p></div><div className="actions"><button className="btn btn-secondary" onClick={() => { void classes.refetch(); if (classId) { void detail.refetch(); void queryClient.invalidateQueries({ queryKey: ['student-teaching-content', user?.id, classId] }); } }}>刷新数据</button><button className="btn btn-secondary" onClick={() => void logout()}>退出登录</button></div></header>
    {classes.isLoading ? <LoadingState /> : classes.error ? <ErrorState message={classes.error.message} retry={() => void classes.refetch()} /> : !classes.data?.items.length ? <EmptyState title="暂无班级" description="请联系任课老师确认是否在班级名单中。" /> : <>
      <label className="field"><span>课程班级</span><select value={classId} onChange={(e) => setParams({ class: e.target.value }, { replace: true })}><option value="" disabled>请选择要进入的课程</option>{classes.data.items.map((item) => <option key={item.id} value={item.id}>{[item.course_name, item.name, item.term, item.teacher_name].filter(Boolean).join(' · ')}</option>)}</select></label>
      {selectedClass?.can_record_scores && <p><Link className="btn btn-primary" to={`/student/monitor/${classId}`}>班长登记授权项目</Link></p>}
      {selectedClass?.can_review_registrations && <p><Link className="btn btn-secondary" to={`/student/registrations/${classId}`}>审核本班学生注册</Link></p>}
      {classId && <StudentTeachingContent key={classId} classId={classId} />}
      {classId && (detail.isLoading ? <LoadingState /> : detail.error ? <ErrorState message={detail.error.message} retry={() => void detail.refetch()} /> : data && <>
        <section className="panel" style={{ padding: 20, marginTop: 20 }}><h2>本人考勤</h2>{!data.attendance_visible ? <p>老师暂未开放考勤查看</p> : !data.attendance?.length ? <p>暂无考勤记录</p> : <div className="table-scroll"><table><thead><tr><th>日期</th><th>考勤状态</th><th>课堂记录状态</th></tr></thead><tbody>{data.attendance.map((row) => <tr key={row.id}><td>{row.date}</td><td>{attendanceLabels[row.status] ?? row.status}</td><td>{row.session_status === 'COMPLETED' ? '已完成' : '进行中，记录可能更新'}</td></tr>)}</tbody></table></div>}</section>
        <section className="panel" style={{ padding: 20, marginTop: 20 }}><h2>本人平时分</h2>{data.score_visibility === 'HIDDEN' ? <p>老师暂未开放平时分查看</p> : <>
          <p>当前总分：<strong>{displayScore(data.score?.final_score)}</strong></p><p className="form-note">当前计算结果，随教师录入更新。{data.score?.status === 'RULES_PENDING' ? '评分规则尚未配置完整，暂不能生成总分。' : data.score?.status === 'RECORDS_PENDING' ? '还有待评价项目，目前按 0 分计入。' : ''}</p>
          {data.details && <>
            <h3>评分规则</h3><p>基础分：{displayPoints(data.details.settings.base_score)}；最终总分限制在 0～100 分。</p><p>{categories.map((category) => `${category.label}：每积分折合 ${displayPoints(data.details!.settings.factors[category.key])} 分`).join('；')}</p>
            <h3>项目明细</h3><div className="table-scroll"><table><thead><tr><th>日期</th><th>项目</th><th>类别</th><th>积分</th><th>备注 / 说明</th></tr></thead><tbody>{data.details.items.map((item) => {
              const record = data.details!.records.find((row) => row.item_id === item.id); const points = record ? record.points : item.default_points;
              return <tr key={item.id}><td>{item.occurred_on}</td><td>{item.name}</td><td>{categories.find((category) => category.key === item.category)?.label}</td><td>{points == null ? '待评价' : displayPoints(points)}</td><td>{record?.note || item.description || '—'}</td></tr>;
            })}</tbody></table></div>
            <h3>类别累计</h3><p>{data.details.summary?.categories.map((category) => `${categories.find((item) => item.key === category.category)?.label}：${displayPoints(category.points)} 积分`).join('；')}</p>
          </>}
        </>}</section>
      </>)}
    </>}
  </main>;
}
