import { Link } from 'react-router-dom';
import { ConnectionBadge } from '../../components/common/ConnectionBadge';

const workspaces = [
  {
    title: 'پایگاه کد',
    description: 'نمایش آزمایشی پردازش یک مخزن کد.',
    to: '/codebase',
  },
  {
    title: 'ورود اسناد',
    description: 'آماده‌سازی و نمایش آزمایشی اسناد.',
    to: '/documents',
  },
  {
    title: 'پرسش‌وپاسخ',
    description: 'مشاهده پاسخ نمونه و منابع نمایشی.',
    to: '/qa',
  },
];

export function OverviewPage() {
  return (
    <section className="page-content" aria-labelledby="overview-title">
      <p className="eyebrow">نمای کلی</p>
      <h1 id="overview-title">به دموی همتایار خوش آمدید</h1>
      <p className="page-intro">
        این محیط برای نمایش جریان‌های کاری ساخته شده است. نتیجه‌های نمایشی در سرور ثبت
        نمی‌شوند.
      </p>

      <div className="workspace-grid">
        {workspaces.map((workspace) => (
          <article className="workspace-card" key={workspace.to}>
            <h2>{workspace.title}</h2>
            <p>{workspace.description}</p>
            <Link className="text-link" to={workspace.to}>
              رفتن به فضا <span aria-hidden="true">←</span>
            </Link>
          </article>
        ))}
      </div>

      <section className="connection-panel" aria-labelledby="connection-title">
        <h2 id="connection-title">وضعیت اتصال</h2>
        <p>وضعیت سرویس‌ها هنوز بررسی نشده است؛ نتیجه‌های نمایشی مستقل از آن‌ها هستند.</p>
        <div className="connection-panel__badges">
          <ConnectionBadge service="همتایار" status="unknown" />
          <ConnectionBadge service="پردازش کد" status="unknown" />
        </div>
      </section>
    </section>
  );
}
