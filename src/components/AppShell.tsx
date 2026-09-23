import { BookOpen, ClipboardCheck, GraduationCap, LayoutDashboard, LogOut, UsersRound } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../app/auth';

const links = [
  { to: '/', label: '工作台', icon: LayoutDashboard, end: true },
  { to: '/courses', label: '课程班级', icon: BookOpen },
  { to: '/classes/current/roster', label: '学生名单', icon: UsersRound },
  { to: '/records', label: '考勤记录', icon: ClipboardCheck },
  { to: '/scores', label: '平时成绩', icon: GraduationCap },
];
export function AppShell() {
  const { user, logout } = useAuth();
  return <div className="app-shell"><a className="skip-link" href="#main-content">跳到主要内容</a>
    <aside className="sidebar" aria-label="主导航"><NavLink className="brand" to="/"><span className="brand-mark" aria-hidden="true">课</span><span>课点</span></NavLink><p className="nav-label">教学管理</p><nav className="primary-nav">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><Icon aria-hidden="true" /><span>{label}</span></NavLink>)}</nav><div className="sidebar-user"><span className="avatar">{user?.display_name?.slice(0, 1) || '师'}</span><span><strong>{user?.display_name || '教师'}</strong><small>{user?.username}</small></span><button className="icon-btn" type="button" onClick={() => void logout()} aria-label="退出登录" title="退出登录"><LogOut aria-hidden="true" /></button></div></aside>
    <header className="mobile-header"><NavLink className="brand" to="/"><span className="brand-mark">课</span><span>课点</span></NavLink><span>{user?.display_name}</span></header>
    <main id="main-content" className="app-content"><Outlet /></main>
    <nav className="mobile-nav" aria-label="移动端主导航">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end}><Icon aria-hidden="true" /><span>{label}</span></NavLink>)}</nav>
  </div>;
}
