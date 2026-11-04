import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { signOut } from '../features/auth/authService';
import { ModeSelector } from '../components/common/ModeSelector';

const navigation = [
  { to: '/', label: 'نمای کلی', end: true },
  { to: '/codebase', label: 'پایگاه کد' },
  { to: '/documents', label: 'ورود اسناد' },
  { to: '/qa', label: 'پرسش‌وپاسخ' },
  { to: '/settings/metadata', label: 'تنظیم فراداده' },
];

export function DashboardLayout() {
  const navigate = useNavigate();

  function handleLogout() {
    signOut();
    navigate('/login', { replace: true });
  }

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div className="dashboard-brand">
          <span className="dashboard-brand__mark" aria-hidden="true">
            ه
          </span>
          <div>
            <strong>همتایار</strong>
            <span>محیط آزمایشی</span>
          </div>
        </div>
        <div className="dashboard-header__actions">
          <ModeSelector />
          <button className="button button--quiet" onClick={handleLogout} type="button">
            خروج
          </button>
        </div>
      </header>

      <div className="dashboard-body">
        <aside className="sidebar" aria-label="پیمایش اصلی">
          <nav>
            {navigation.map(({ to, label, end }) => (
              <NavLink
                className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}
                end={end}
                key={to}
                to={to}
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="dashboard-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
