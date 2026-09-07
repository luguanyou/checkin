import { describe, expect, it } from 'vitest';
import { attendanceActionForKey, canCompleteSession, clampIndex, firstPendingIndex, summarizeRecords } from './attendance-state';
import type { AttendanceRecord } from '../../api/types';

const record = (status: AttendanceRecord['status']): AttendanceRecord => ({
  id: status, student_id: status, student_number: '1', student_name: status, class_name: '班级', status,
  marked_at: null, last_modified_at: null, last_modified_by: { id: 'u', display_name: '教师' }, version: 1,
});

describe('attendance state', () => {
  it('starts from the first pending record and clamps indexes', () => {
    const records = [record('present'), record('pending'), record('pending')];
    expect(firstPendingIndex(records)).toBe(1);
    expect(clampIndex(-1, records.length)).toBe(0);
    expect(clampIndex(5, records.length)).toBe(2);
  });

  it('maps shortcuts and excludes editable targets', () => {
    expect(attendanceActionForKey(' ')).toBe('present');
    expect(attendanceActionForKey('3')).toBe('late');
    expect(attendanceActionForKey('Backspace')).toBe('previous');
    expect(attendanceActionForKey('1', true)).toBeNull();
  });

  it('summarizes records and allows pending records when changes are synced', () => {
    const records = [record('present'), record('late'), record('absent'), record('pending')];
    expect(summarizeRecords(records)).toMatchObject({ total: 4, processed: 3, pending: 1, exceptions: 2, attendanceRate: 67 });
    expect(canCompleteSession(records, 0, 0)).toBe(true);
    expect(canCompleteSession(records.slice(0, 3), 1, 0)).toBe(false);
    expect(canCompleteSession(records.slice(0, 3), 0, 0)).toBe(true);
  });
});
