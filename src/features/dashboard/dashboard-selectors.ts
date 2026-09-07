import type { AttendanceSessionBase, Course } from '../../api/types';

export function deriveDashboardMetrics(courses: Course[], sessions: AttendanceSessionBase[]) {
  const activeCourses = courses.filter((course) => course.status === 'ACTIVE');
  const processed = sessions.reduce((sum, session) => sum + session.summary.total - session.summary.pending, 0);
  const attended = sessions.reduce((sum, session) => sum + session.summary.present + session.summary.late, 0);
  return {
    activeCourses: activeCourses.length,
    activeClasses: activeCourses.reduce((sum, course) => sum + course.classes.filter((item) => item.status === 'ACTIVE').length, 0),
    draftSessions: sessions.filter((session) => session.status === 'DRAFT').length,
    attendanceRate: processed ? Math.round(attended / processed * 100) : 0,
  };
}
