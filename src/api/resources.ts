import type {
  AdminUserListParams,
  AttendanceRecord,
  AttendanceSession,
  AttendanceSessionBase,
  AttendanceSessionPage,
  ClassGroup,
  Course,
  CoursePage,
  CreateTeacherInput,
  ImportPreview,
  ImportResult,
  LoginResponse,
  RosterMember,
  RosterPage,
  User,
  UserPage,
  UserStatus,
} from './types';
import { ApiClient } from './client';

function queryString(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : '';
}

function json(method: string, body?: unknown): RequestInit {
  return { method, body: body === undefined ? undefined : JSON.stringify(body) };
}

export function createApi(client: ApiClient) {
  return {
    auth: {
      login: (username: string, password: string) => client.request<LoginResponse>('/auth/login', json('POST', { username, password }), false),
      refresh: () => client.request<LoginResponse>('/auth/refresh', { method: 'POST' }, false),
      logout: () => client.request<void>('/auth/logout', { method: 'POST' }, false),
      me: () => client.request<User>('/auth/me'),
      changePassword: (current_password: string, new_password: string) => client.request<LoginResponse>('/auth/change-password', json('POST', { current_password, new_password })),
    },
    adminUsers: {
      list: (params: AdminUserListParams = {}) => client.request<UserPage>(`/admin/users${queryString(params)}`),
      create: (input: CreateTeacherInput) => client.request<User>('/admin/users', json('POST', input)),
      updateStatus: (userId: string, status: UserStatus) => client.request<User>(`/admin/users/${userId}/status`, json('PATCH', { status })),
      resetPassword: (userId: string, temporary_password: string) => client.request<void>(`/admin/users/${userId}/reset-password`, json('POST', { temporary_password })),
    },
    courses: {
      list: (params: { page?: number; page_size?: number; status?: string; term?: string; q?: string } = {}) => client.request<CoursePage>(`/courses${queryString(params)}`),
      create: (input: { name: string; code: string; term: string }) => client.request<Course>('/courses', json('POST', input)),
      update: (id: string, input: Partial<Pick<Course, 'name' | 'code' | 'term' | 'status'>>) => client.request<Course>(`/courses/${id}`, json('PATCH', input)),
      createClass: (courseId: string, name: string) => client.request(`/courses/${courseId}/classes`, json('POST', { name })),
      updateClass: (classId: string, input: { name?: string; status?: string }) => client.request<ClassGroup>(`/classes/${classId}`, json('PATCH', input)),
      delete: (id: string) => client.request<void>(`/courses/${id}`, { method: 'DELETE' }),
      deleteClass: (classId: string, deleteRelatedData = false) => client.request<void>(
        `/classes/${classId}${queryString({ delete_related_data: deleteRelatedData ? 'true' : undefined })}`,
        { method: 'DELETE' },
      ),
    },
    roster: {
      list: (classId: string, params: { page?: number; page_size?: number; status?: string; q?: string } = {}) => client.request<RosterPage>(`/classes/${classId}/roster${queryString(params)}`),
      updateStatus: (enrollmentId: string, status: 'ACTIVE' | 'REMOVED') => client.request<RosterMember>(`/enrollments/${enrollmentId}/status`, json('PATCH', { status })),
      preview: (classId: string, file: File) => {
        const form = new FormData();
        form.append('file', file);
        return client.request<ImportPreview>(`/classes/${classId}/roster/import-preview`, { method: 'POST', body: form });
      },
      confirm: (classId: string, preview_id: string, duplicate_policy: 'skip' | 'replace') => client.request<ImportResult>(`/classes/${classId}/roster/import-confirm`, json('POST', { preview_id, duplicate_policy })),
    },
    attendance: {
      list: (params: Record<string, string | number | undefined> = {}) => client.request<AttendanceSessionPage>(`/attendance-sessions${queryString(params)}`),
      create: (classId: string, session_date: string) => client.request<AttendanceSession>(`/classes/${classId}/attendance-sessions`, json('POST', { session_date })),
      get: (sessionId: string) => client.request<AttendanceSession>(`/attendance-sessions/${sessionId}`),
      updateRecord: (recordId: string, input: { status: string; expected_version: number; client_mutation_id: string; reason?: string }) => client.request<AttendanceRecord>(`/attendance-records/${recordId}`, json('PATCH', input)),
      complete: (sessionId: string) => client.request<AttendanceSessionBase>(`/attendance-sessions/${sessionId}/complete`, { method: 'POST' }),
      export: (sessionId: string, format: 'csv' | 'xlsx') => client.download(`/attendance-sessions/${sessionId}/export?format=${format}`),
    },
  };
}

export type AttendanceApi = ReturnType<typeof createApi>;
