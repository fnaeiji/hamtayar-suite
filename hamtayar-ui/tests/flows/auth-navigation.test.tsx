import { useState } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { AppRoutes } from '../../src/app/router';
import { ModeProvider, useMode } from '../../src/app/ModeProvider';
import { operationManager } from '../../src/services/operations/operationManager';

function renderApp(initialEntry = '/', withOperationHarness = false) {
  return render(
    <ModeProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        {withOperationHarness && <OperationHarness />}
        <AppRoutes />
      </MemoryRouter>
    </ModeProvider>,
  );
}

function OperationHarness() {
  const navigate = useNavigate();
  const { mode, canSwitchMode, switchMode } = useMode();
  const [updateAccepted, setUpdateAccepted] = useState<boolean | null>(null);
  const operation = operationManager.get('flow-test');

  function startPending() {
    const record = operationManager.begin('flow-test', mode);
    operationManager.update(record.id, record.generation, { status: 'pending' });
  }

  function startReplacement() {
    const old = operationManager.get('flow-test');
    if (!old) return;
    operationManager.update(old.id, old.generation, { status: 'completed' });
    const replacement = operationManager.begin('flow-test', mode);
    setUpdateAccepted(
      operationManager.update(old.id, old.generation, {
        status: 'completed',
        result: 'stale',
      }),
    );
    operationManager.update(replacement.id, replacement.generation, {
      status: 'pending',
    });
  }

  return (
    <section>
      <p>حالت فعلی: {mode === 'demo' ? 'نمایشی' : 'API'}</p>
      <p>عملیات: {operation?.status ?? 'بدون عملیات'}</p>
      <button onClick={() => navigate('/codebase')} type="button">
        رفتن به همتایار کد
      </button>
      <button onClick={() => navigate('/')} type="button">
        بازگشت به نمای کلی
      </button>
      <button onClick={startPending} type="button">
        شروع عملیات معلق
      </button>
      <button onClick={startReplacement} type="button">
        آغاز نسل تازه
      </button>
      <button disabled={!canSwitchMode} onClick={() => switchMode('api')} type="button">
        تغییر به API
      </button>
      <output aria-label="نتیجه به‌روزرسانی قدیمی">
        {updateAccepted === null ? 'نامشخص' : String(updateAccepted)}
      </output>
    </section>
  );
}

describe('demo login and navigation flow', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    operationManager.logout();
  });

  afterEach(() => {
    cleanup();
    operationManager.logout();
    window.sessionStorage.clear();
  });

  it('accepts the fixed demo credentials and identifies the environment as experimental', async () => {
    const user = userEvent.setup();
    renderApp('/login');

    await user.type(screen.getByLabelText('نام کاربری'), 'demo');
    await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));

    expect(
      await screen.findByRole('heading', { name: 'به دموی همتایار خوش آمدید' }),
    ).toBeVisible();
    expect(screen.getByText('محیط آزمایشی')).toBeVisible();
    expect(window.sessionStorage.getItem('hamtayar-demo-ui.session.v1')).not.toContain(
      'Hamtayar123!',
    );
  });

  it('rejects invalid credentials without leaving login', async () => {
    const user = userEvent.setup();
    renderApp('/login');

    await user.type(screen.getByLabelText('نام کاربری'), 'someone');
    await user.type(screen.getByLabelText('گذرواژه'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'نام کاربری یا گذرواژه نادرست است',
    );
    expect(screen.getByRole('heading', { name: 'ورود به دموی همتایار' })).toBeVisible();
    expect(window.sessionStorage.getItem('hamtayar-demo-ui.session.v1')).toBeNull();
  });

  it('guards workspace routes and preserves the tab session after remount', async () => {
    const user = userEvent.setup();
    const firstRender = renderApp('/documents');
    expect(
      await screen.findByRole('heading', { name: 'ورود به دموی همتایار' }),
    ).toBeVisible();

    await user.type(screen.getByLabelText('نام کاربری'), 'demo');
    await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));
    expect(await screen.findByRole('heading', { name: 'ورود اسناد' })).toBeVisible();
    firstRender.unmount();

    renderApp('/documents');
    expect(await screen.findByRole('heading', { name: 'ورود اسناد' })).toBeVisible();
  });

  it('navigates every workspace and shows the active mode', async () => {
    const user = userEvent.setup();
    renderApp('/');
    await user.type(screen.getByLabelText('نام کاربری'), 'demo');
    await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));

    expect(screen.getByLabelText('حالت اجرا')).toHaveValue('demo');
    expect(screen.getByRole('link', { name: 'همتایار کد' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:5173/',
    );
    expect(screen.queryByRole('link', { name: 'تنظیم فراداده' })).not.toBeInTheDocument();
    for (const [linkName, heading] of [
      ['ورود اسناد', 'ورود اسناد'],
      ['پرسش‌وپاسخ', 'پرسش‌وپاسخ'],
      ['نمای کلی', 'به دموی همتایار خوش آمدید'],
    ]) {
      await user.click(screen.getByRole('link', { name: new RegExp(linkName) }));
      expect(await screen.findByRole('heading', { name: heading })).toBeVisible();
    }
  });

  it('logs out, clears temporary operations, and stops registered local observers', async () => {
    const user = userEvent.setup();
    const stopObserver = vi.fn();
    const active = operationManager.begin('temporary', 'demo');
    operationManager.update(active.id, active.generation, { status: 'pending' });
    operationManager.registerCleanup(active.id, stopObserver);
    renderApp('/login');

    await user.type(screen.getByLabelText('نام کاربری'), 'demo');
    await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));
    await user.click(screen.getByRole('button', { name: 'خروج' }));

    expect(
      await screen.findByRole('heading', { name: 'ورود به دموی همتایار' }),
    ).toBeVisible();
    expect(window.sessionStorage.getItem('hamtayar-demo-ui.session.v1')).toBeNull();
    expect(operationManager.getSnapshot()).toHaveLength(0);
    expect(stopObserver).toHaveBeenCalledTimes(1);
  });

  it('retains a pending operation across workspace navigation and rejects stale updates', async () => {
    const user = userEvent.setup();
    renderApp('/', true);
    await user.type(screen.getByLabelText('نام کاربری'), 'demo');
    await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));
    await user.click(screen.getByRole('button', { name: 'شروع عملیات معلق' }));
    expect(screen.getByText('عملیات: pending')).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'حالت اجرا' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'رفتن به همتایار کد' }));
    expect(await screen.findByRole('heading', { name: 'همتایار کد' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'بازگشت به نمای کلی' }));
    expect(screen.getByText('عملیات: pending')).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'آغاز نسل تازه' }));
    expect(screen.getByLabelText('نتیجه به‌روزرسانی قدیمی')).toHaveTextContent('false');
  });

  it('blocks mode switching while pending and updates the active mode after completion', async () => {
    const user = userEvent.setup();
    renderApp('/', true);
    await user.type(screen.getByLabelText('نام کاربری'), 'demo');
    await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
    await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));
    await user.click(screen.getByRole('button', { name: 'شروع عملیات معلق' }));
    expect(screen.getByRole('button', { name: 'تغییر به API' })).toBeDisabled();
    const pending = operationManager.get('flow-test');
    expect(pending).toBeDefined();
    operationManager.update('flow-test', pending!.generation, { status: 'completed' });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'تغییر به API' })).toBeEnabled(),
    );
    await user.selectOptions(screen.getByRole('combobox', { name: 'حالت اجرا' }), 'api');
    expect(screen.getByRole('combobox', { name: 'حالت اجرا' })).toHaveValue('api');
    expect(screen.getByText('حالت فعلی: API')).toBeVisible();
  });
});
