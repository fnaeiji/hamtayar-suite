import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { signOut } from '../features/auth/authService';
import { ModeSelector } from '../components/common/ModeSelector';
import { WorkspaceIcon } from '../components/common/WorkspaceIcon';
import { codeWorkspaceUrl } from '../config/codeWorkspace';
const navigation = [
  { to: '/', label: 'نمای کلی', icon: 'overview' },
  { to: '/documents', label: 'ورود اسناد', icon: 'documents' },
  { to: '/qa', label: 'پرسش‌وپاسخ', icon: 'qa' },
];
export function DashboardLayout() {
  const navigate = useNavigate();
  return (
    <div className="dashboard-shell">
      <aside className="sidebar" aria-label="پیمایش اصلی">
        <div className="dashboard-brand">
          <span className="dashboard-brand__mark">
            <WorkspaceIcon kind="code" />
          </span>
          <div>
            <strong>همتایار</strong>
            <span dir="ltr">KNOWLEDGE WORKSPACE</span>
          </div>
        </div>
        <p className="workspace-label">فضاهای کاری</p>
        <nav>
          {navigation.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `nav-link${isActive ? ' nav-link--active' : ''}`
              }
            >
              <WorkspaceIcon kind={icon} />
              {label}
            </NavLink>
          ))}
          <a className="nav-link" href={codeWorkspaceUrl ?? '/codebase'}>
            <WorkspaceIcon kind="code" />
            <span>همتایار کد</span>
            <span className="external-arrow" aria-hidden="true">
              ↖
            </span>
          </a>
        </nav>
        <div className="sidebar-bottom">
          <span className="environment-dot" />
          محیط آزمایشی<small>دانش سازمان، در یک فضای مشترک</small>
        </div>
      </aside>
      <div className="dashboard-workspace">
        <header className="dashboard-header">
          <div>
            <span className="eyebrow">HAMTAYAR / WORKSPACE</span>
            <span className="header-caption">فضای دانش سازمان</span>
          </div>
          <div className="dashboard-header__actions">
            <ModeSelector />
            <button
              className="button button--quiet"
              onClick={() => {
                signOut();
                navigate('/login', { replace: true });
              }}
              type="button"
            >
              خروج
            </button>
          </div>
        </header>
        <main className="dashboard-main">
          <Outlet />
        </main>
        <footer className="workspace-footer">همتایار · محیط آزمایشی مدیریت دانش</footer>
      </div>
    </div>
  );
}
