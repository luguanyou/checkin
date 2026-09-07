import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { LoginPage } from '../features/auth/LoginPage';
import { ChangePasswordPage } from '../features/auth/ChangePasswordPage';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { CoursesPage } from '../features/courses/CoursesPage';
import { RosterPage } from '../features/roster/RosterPage';
import { AttendancePage } from '../features/attendance/AttendancePage';
import { RecordsPage } from '../features/records/RecordsPage';
import { RecordDetailPage } from '../features/records/RecordDetailPage';
import { AdminPage } from '../features/admin/AdminPage';
import type { UserRole } from '../api/types';
import { useAuth } from './auth';

function Boot() { return <div className="boot-state" role="status">正在恢复登录状态...</div>; }
function homeFor(role: UserRole | undefined) { return role === 'ADMIN' ? '/admin' : '/'; }
function ProtectedRoute() {
  const { status, user } = useAuth(); const location = useLocation();
  if (status === 'restoring') return <Boot />;
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />;
  if (user?.must_change_password) return <Navigate to="/change-password" replace />;
  return <Outlet />;
}
function PublicOnly({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  if (status === 'restoring') return <Boot />;
  if (status === 'authenticated') return <Navigate to={user?.must_change_password ? '/change-password' : homeFor(user?.role)} replace />;
  return children;
}
function PasswordRoute() {
  const { status, user } = useAuth();
  if (status === 'restoring') return <Boot />;
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  if (!user?.must_change_password) return <Navigate to={homeFor(user?.role)} replace />;
  return <ChangePasswordPage />;
}
function RoleRoute({ role }: { role: UserRole }) {
  const { user } = useAuth();
  if (user?.role !== role) return <Navigate to={homeFor(user?.role)} replace />;
  return <Outlet />;
}
export function AppRoutes() {
  return <Routes>
    <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
    <Route path="/change-password" element={<PasswordRoute />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<RoleRoute role="ADMIN" />}>
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route element={<RoleRoute role="TEACHER" />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="courses" element={<CoursesPage />} />
          <Route path="classes/:classId/roster" element={<RosterPage />} />
          <Route path="records" element={<RecordsPage />} />
          <Route path="records/:sessionId" element={<RecordDetailPage />} />
        </Route>
        <Route path="attendance/:sessionId" element={<AttendancePage />} />
      </Route>
    </Route>
    <Route path="*" element={<main className="not-found"><h1>页面不存在</h1><a href="/">返回工作台</a></main>} />
  </Routes>;
}
