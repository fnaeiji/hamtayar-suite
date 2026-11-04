import { StatusMessage } from '../components/common/StatusMessage';

export function WorkspacePlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="page-content" aria-labelledby="workspace-title">
      <p className="eyebrow">فضای کاری</p>
      <h1 id="workspace-title">{title}</h1>
      <p className="page-intro">{description}</p>
      <StatusMessage tone="info" title="آماده‌سازی محیط آزمایشی">
        محتوای این بخش در حال آماده‌سازی است. این صفحه به سرویس پشتیبان درخواست نمی‌فرستد.
      </StatusMessage>
    </section>
  );
}
