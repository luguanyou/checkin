import { describe, expect, it } from 'vitest';
import { deriveDashboardMetrics } from './dashboard-selectors';
import type { AttendanceSessionBase, Course } from '../../api/types';

describe('deriveDashboardMetrics', () => {
  it('derives course, class, draft, and attendance metrics', () => {
    const courses = [{ status: 'ACTIVE', classes: [{ status: 'ACTIVE' }, { status: 'ACTIVE' }] }, { status: 'ARCHIVED', classes: [{ status: 'ACTIVE' }] }] as Course[];
    const sessions = [
      { status: 'DRAFT', summary: { total: 10, pending: 2, present: 5, absent: 1, leave: 1, late: 1, exceptions: 2 } },
      { status: 'COMPLETED', summary: { total: 8, pending: 0, present: 6, absent: 1, leave: 0, late: 1, exceptions: 2 } },
    ] as AttendanceSessionBase[];
    expect(deriveDashboardMetrics(courses, sessions)).toEqual({ activeCourses: 1, activeClasses: 2, draftSessions: 1, attendanceRate: 81 });
  });

  it('returns zeros for empty data', () => {
    expect(deriveDashboardMetrics([], [])).toEqual({ activeCourses: 0, activeClasses: 0, draftSessions: 0, attendanceRate: 0 });
  });
});
