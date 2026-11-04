import { codeWorkspaceUrl } from '../../config/codeWorkspace';
export function CodebasePage() {
  return (
    <section className="page-content">
      <p className="eyebrow">HAMTAYAR / CODE INTELLIGENCE</p>
      <h1>همتایار کد</h1>
      <div className="workspace-card">
        <h2>ورود به فضای تحلیل کد</h2>
        <p>
          این بخش از همان برنامه HamtayarDemo در پوشه CGC استفاده می‌کند؛ مرور کد، گراف
          وابستگی و پرسش و کانتکست در آن قرار دارند.
        </p>
        {codeWorkspaceUrl ? (
          <a className="button button--primary" href={codeWorkspaceUrl}>
            باز کردن همتایار کد ↖
          </a>
        ) : (
          <p role="alert">آدرس محلی رابط کد معتبر نیست؛ VITE_CGC_UI_URL را بررسی کنید.</p>
        )}
        <p>اگر صفحه باز نشد، ابتدا برنامه کد را اجرا کنید:</p>
        <pre dir="ltr">{'cd ..\\CGC\\HamtayarDemo\n.\\scripts\\start-dev.ps1'}</pre>
        <p>رابط کد: پورت ۵۱۷۳ · رابط اصلی: پورت ۵۱۷۴</p>
        <p className="muted">
          شروع این برنامه به آماده بودن محیط Python، CGC و Neo4j مطابق راهنمای همان پوشه
          نیاز دارد.
        </p>
      </div>
    </section>
  );
}
