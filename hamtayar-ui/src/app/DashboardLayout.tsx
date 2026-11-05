import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { signOut } from '../features/auth/authService';
import { ModeSelector } from '../components/common/ModeSelector';
import { WorkspaceIcon } from '../components/common/WorkspaceIcon';
import { codePages } from '../features/codebase/navigation';
import { workspaces } from './workspaces';
export function DashboardLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const isCode = location.pathname.startsWith('/codebase');
  return (
    <div className="dashboard-shell">
      <aside className="sidebar" aria-label="پیمایش اصلی">
        <NavLink to="/" className="dashboard-brand" aria-label="خانه همتایار">
          <span className="dashboard-brand__mark">
            <WorkspaceIcon kind="overview" />
          </span>
          <div>
            <strong>همتایار</strong>
            <span>فضای یکپارچه دانش سازمان</span>
          </div>
        </NavLink>
        <p className="workspace-label">دسترسی به فضاهای کاری</p>
        <nav aria-label="بخش‌های داشبورد">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}
          >
            <WorkspaceIcon kind="overview" />
            داشبورد
          </NavLink>
          {workspaces.map((workspace) => (
            <div key={workspace.to}>
              <NavLink
                to={workspace.to}
                className={({ isActive }) =>
                  `nav-link${isActive || (workspace.icon === 'code' && isCode) ? ' nav-link--active' : ''}`
                }
                aria-expanded={workspace.icon === 'code' ? isCode : undefined}
              >
                <WorkspaceIcon kind={workspace.icon} />
                <span>{workspace.title}</span>
                {workspace.icon === 'code' && (
                  <span className="submenu-caret" aria-hidden="true">
                    {isCode ? '⌄' : '‹'}
                  </span>
                )}
              </NavLink>
              {workspace.icon === 'code' && isCode && (
                <nav className="code-submenu" aria-label="زیرمنوهای پردازش کدبیس">
                  {codePages.map(([id, label]) => (
                    <NavLink
                      key={id}
                      to={'/codebase/' + id}
                      className={({ isActive }) =>
                        isActive ? 'code-submenu__active' : ''
                      }
                    >
                      {label}
                    </NavLink>
                  ))}
                </nav>
              )}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="environment-dot" />
          محیط آزمایشی<small>اسناد و کد، در یک داشبورد</small>
        </div>
      </aside>
      <div className="dashboard-workspace">
        <header className="dashboard-header">
          <div>
            <span className="eyebrow">HAMTAYAR / KNOWLEDGE PLATFORM</span>
            <span className="header-caption">
              {isCode ? 'همتایار کد' : 'سامانه دانش سازمانی همتایار'}
            </span>
          </div>
          <div className="dashboard-header__actions">
            {isCode ? (
              <span className="quiet-badge">سرویس محلی پردازش کد</span>
            ) : (
              <ModeSelector />
            )}
            <button
              className="button button--quiet"
              type="button"
              onClick={() => {
                signOut();
                navigate('/login', { replace: true });
              }}
            >
              خروج
            </button>
          </div>
        </header>
        <main className="dashboard-main">
          <Outlet />
        </main>
        <footer className="workspace-footer">همتایار · فضای یکپارچه اسناد و کد</footer>
      </div>
    </div>
  );
}
