import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { WorkspaceIcon } from '../../components/common/WorkspaceIcon';
import { hasDemoSession, signIn } from './authService';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();

  if (hasDemoSession()) return <Navigate to="/" replace />;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (!signIn(username, password)) {
      setError(
        username === 'demo' && password === 'Hamtayar123!'
          ? 'مرورگر اجازه ذخیره نشست آزمایشی را نداد. تنظیمات ذخیره‌سازی مرورگر را بررسی کنید.'
          : 'نام کاربری یا گذرواژه نادرست است.',
      );
      return;
    }

    const destination = (location.state as { from?: { pathname?: string } } | null)?.from
      ?.pathname;
    navigate(destination || '/', { replace: true });
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand">
          <WorkspaceIcon kind="overview" />
          <span>همتایار</span>
        </div>
        <p className="eyebrow">محیط آزمایشی</p>
        <h1 id="login-title">ورود به دموی همتایار</h1>
        <p className="login-card__description">
          این ورود فقط برای نمایش رابط کاربری است و به سرویس‌های پشتیبان احراز هویت
          نمی‌کند.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            نام کاربری
            <input
              autoComplete="username"
              name="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            گذرواژه
            <input
              autoComplete="current-password"
              name="password"
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button className="button button--primary" type="submit">
            ورود به محیط آزمایشی
          </button>
        </form>
      </section>
    </main>
  );
}
