export type UserRole = 'ADMIN' | 'TEACHER';
export type UserStatus = 'ACTIVE' | 'DISABLED';
export type ResourceStatus = 'ACTIVE' | 'ARCHIVED';
export type EnrollmentStatus = 'ACTIVE' | 'REMOVED';
export type SessionStatus = 'DRAFT' | 'COMPLETED';
export type AttendanceStatus = 'pending' | 'present' | 'absent' | 'leave' | 'late';

export interface ErrorResponse {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
}

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

export interface ClassGroup {
  id: string;
  name: string;
  status: ResourceStatus;
  active_student_count: number;
}

export interface Course {
  id: string;
  name: string;
  code: string;
  term: string;
  status: ResourceStatus;
  classes: ClassGroup[];
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export type UserPage = Page<User>;

export interface AdminUserListParams {
  [key: string]: string | number | undefined;
  page?: number;
  page_size?: number;
  role?: UserRole;
  status?: UserStatus;
  q?: string;
}

export interface CreateTeacherInput {
  username: string;
  display_name: string;
  temporary_password: string;
}

export interface Student {
  id: string;
  student_number: string;
  name: string;
  gender: string | null;
  major: string | null;
}

export interface RosterMember {
  enrollment_id: string;
  enrollment_status: EnrollmentStatus;
  student: Student;
  created_at: string;
  updated_at: string;
}

export interface ImportSummary {
  total: number;
  valid: number;
  errors: number;
  duplicates: number;
  importable: number;
}

export interface ImportRow {
  row_number: number;
  student_number: string;
  name: string;
  gender: string | null;
  class_name: string;
  major: string | null;
  status: string;
  code: string | null;
  fields: string[];
  message: string | null;
}

export interface ImportPreview {
  preview_id: string;
  expires_at: string;
  summary: ImportSummary;
  rows: ImportRow[];
}

export interface ImportResult {
  preview_id: string;
  created_students: number;
  created_enrollments: number;
  restored_enrollments: number;
  skipped: number;
  failed: number;
}

export interface AttendanceSummary {
  total: number;
  pending: number;
  present: number;
  absent: number;
  leave: number;
  late: number;
  exceptions: number;
}

export interface AttendanceRecord {
  id: string;
  student_id: string;
  student_number: string;
  student_name: string;
  class_name: string;
  status: AttendanceStatus;
  marked_at: string | null;
  last_modified_at: string | null;
  last_modified_by: { id: string; display_name: string };
  version: number;
}

export interface AttendanceSessionBase {
  id: string;
  course: { id: string; name: string; code: string };
  class_group: { id: string; name: string };
  session_date: string;
  status: SessionStatus;
  started_at: string;
  completed_at: string | null;
  summary: AttendanceSummary;
  created_at: string;
  updated_at: string;
}

export interface AttendanceSession extends AttendanceSessionBase {
  records: AttendanceRecord[];
}

export type CoursePage = Page<Course>;
export type RosterPage = Page<RosterMember>;
export type AttendanceSessionPage = Page<AttendanceSessionBase>;
