import { Link } from 'react-router-dom';
import { WorkspaceIcon } from '../../components/common/WorkspaceIcon';
import { workspaces } from '../../app/workspaces';
import { documentCatalog } from '../../services/documentCatalog';
export function OverviewPage() {
  const catalog = documentCatalog.use();
  return (
    <section className="page-content">
      <div className="hero">
        <div>
          <p className="eyebrow">فضای یکپارچه دانش سازمان</p>
          <h1>به دموی همتایار خوش آمدید</h1>
          <p>
            از سند تا کد، دانشتان را سازمان‌دهی کنید.
            <br />
            پردازش، جستجو و پرسش‌وپاسخ در یک فضای کاری.
          </p>
          <Link className="button button--primary" to="/documents">
            شروع پردازش اسناد <span aria-hidden="true">←</span>
          </Link>
        </div>
        <div className="hero-network" aria-hidden="true">
          <svg viewBox="0 0 240 180" fill="none">
            <path
              d="M120 90 40 40 65 145 120 90 180 35 205 130 120 90 40 40 180 35 M65 145 205 130"
              stroke="currentColor"
            />
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
                fill="#243f5e"
                stroke="currentColor"
                strokeWidth="2"
              />
            ))}
          </svg>
          <span>DOCUMENTS · KNOWLEDGE · CODE</span>
        </div>
      </div>
      <div className="section-heading">
        <h2>چهار مسیر برای کار با دانش</h2>
        <span>فضای موردنظر را انتخاب کنید</span>
      </div>
      <div className="workspace-grid workspace-grid--four">
        {workspaces.map((workspace, index) => (
          <article className="workspace-card" key={workspace.to}>
            <div className="workspace-card__top">
              <span className="workspace-icon">
                <WorkspaceIcon kind={workspace.icon} />
              </span>
              <span className="workspace-number">
                {(index + 1).toLocaleString('fa-IR', { minimumIntegerDigits: 2 })}
              </span>
            </div>
            <h2>{workspace.title}</h2>
            <p>{workspace.description}</p>
            <Link className="text-link" to={workspace.to}>
              {workspace.action} ←
            </Link>
          </article>
        ))}
      </div>
      <section className="session-summary" aria-label="وضعیت نشست نمایشی">
        <div>
          <span>اسناد ثبت‌شده در این نشست</span>
          <strong>{catalog.documents.length.toLocaleString('fa-IR')}</strong>
        </div>
        <div>
          <span>مراکز این نشست</span>
          <strong>{catalog.centers.length.toLocaleString('fa-IR')}</strong>
        </div>
        <p>
          اطلاعات اسناد دمو در حافظه همین نشست است. پردازش کدبیس به سرویس محلی و تنظیمات
          واقعی آن متصل می‌شود.
        </p>
      </section>
    </section>
  );
}
