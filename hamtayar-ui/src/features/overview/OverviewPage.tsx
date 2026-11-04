import { Link } from 'react-router-dom';
import { WorkspaceIcon } from '../../components/common/WorkspaceIcon';
import { codeWorkspaceUrl } from '../../config/codeWorkspace';
export function OverviewPage() {
  return (
    <section className="page-content">
      <div className="hero">
        <div>
          <p className="eyebrow">ORGANIZATIONAL KNOWLEDGE</p>
          <h1>به دموی همتایار خوش آمدید</h1>
          <p>
            از اسناد تا کد؛ دانش سازمان را یکجا مرور کنید،
            <br />
            سؤال بپرسید و مسیر رسیدن به پاسخ را ببینید.
          </p>
          <Link className="button button--primary" to="/documents">
            شروع با اسناد <span aria-hidden="true">←</span>
          </Link>
        </div>
        <div className="hero-network" aria-hidden="true">
          <svg viewBox="0 0 240 180" fill="none">
            <g stroke="currentColor" strokeWidth="1">
              <path d="M120 90 40 40 65 145 120 90 180 35 205 130 120 90 40 40 180 35 M65 145 205 130" />
            </g>
            {[
              [120, 90, 12],
              [40, 40, 7],
              [65, 145, 7],
              [180, 35, 8],
              [205, 130, 9],
            ].map(([cx, cy, r]) => (
              <circle
                key={cx}
                cx={cx}
                cy={cy}
                r={r}
                fill="#182e4f"
                stroke="currentColor"
                strokeWidth="2"
              />
            ))}
          </svg>
          <span>CONNECTED KNOWLEDGE</span>
        </div>
      </div>
      <div className="section-heading">
        <h2>فضاهای کاری</h2>
        <span>مسیر موردنظرتان را انتخاب کنید</span>
      </div>
      <div className="workspace-grid">
        <article className="workspace-card">
          <span className="workspace-icon">
            <WorkspaceIcon kind="documents" />
          </span>
          <h2>همتایار اسناد</h2>
          <p>اسناد را وارد کنید و مرکز و نوع سند را برای هر فایل مشخص کنید.</p>
          <Link className="text-link" to="/documents">
            باز کردن اسناد ←
          </Link>
        </article>
        <article className="workspace-card">
          <span className="workspace-icon">
            <WorkspaceIcon kind="qa" />
          </span>
          <h2>پرسش‌وپاسخ</h2>
          <p>با انتخاب مرکز و نوع سند، پرسش خود را آماده کنید و پاسخ نمونه را ببینید.</p>
          <Link className="text-link" to="/qa">
            پرسیدن سؤال ←
          </Link>
        </article>
        <article className="workspace-card">
          <span className="workspace-icon">
            <WorkspaceIcon kind="code" />
          </span>
          <h2>همتایار کد</h2>
          <p>ورود به HamtayarDemo برای پردازش کدبیس، کاوش گراف و پرسش از کد.</p>
          <a className="text-link" href={codeWorkspaceUrl ?? '/codebase'}>
            باز کردن همتایار کد ↖
          </a>
        </article>
      </div>
      <div className="connection-panel">
        <div className="panel-heading">
          <h2>آماده برای نمایش</h2>
          <span className="quiet-badge">DEMO WORKSPACE</span>
        </div>
        <p>
          نمایش اسناد و پاسخ نمونه مستقل از سرویس‌هاست. همتایار کد در برنامه جداگانه
          HamtayarDemo اجرا می‌شود.
        </p>
        <Link className="text-link" to="/codebase">
          راهنمای اجرای همتایار کد ←
        </Link>
      </div>
    </section>
  );
}
