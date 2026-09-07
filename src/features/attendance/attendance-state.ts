import type { AttendanceRecord, AttendanceStatus } from '../../api/types';

export type AttendanceAction = Exclude<AttendanceStatus, 'pending'> | 'previous' | 'repeat' | 'mute';

export function attendanceActionForKey(key: string, editable = false): AttendanceAction | null {
  if (editable) return null;
  return ({ ' ': 'present', '1': 'absent', '2': 'leave', '3': 'late', Backspace: 'previous', r: 'repeat', R: 'repeat', m: 'mute', M: 'mute' } as Record<string, AttendanceAction>)[key] ?? null;
}

export function firstPendingIndex(records: AttendanceRecord[]) {
  const index = records.findIndex((record) => record.status === 'pending');
  return index < 0 ? 0 : index;
}

export function clampIndex(index: number, count: number) {
  return count ? Math.max(0, Math.min(index, count - 1)) : 0;
}

export function summarizeRecords(records: AttendanceRecord[]) {
  const counts = { present: 0, absent: 0, leave: 0, late: 0, pending: 0 };
  records.forEach((record) => { counts[record.status] += 1; });
  const processed = records.length - counts.pending;
  return {
    total: records.length,
    processed,
    ...counts,
    exceptions: counts.absent + counts.late,
    attendanceRate: processed ? Math.round((counts.present + counts.late) / processed * 100) : 0,
  };
}

export function canCompleteSession(records: AttendanceRecord[], pendingMutations: number, failedMutations: number) {
  return records.length > 0 && records.every((record) => record.status !== 'pending') && pendingMutations === 0 && failedMutations === 0;
}

export function exceptionRecords(records: AttendanceRecord[]) {
  return records.filter((record) => record.status === 'absent' || record.status === 'late');
}
