import { cleanup, render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { ModeProvider } from '../../src/app/ModeProvider';
import { AppRoutes } from '../../src/app/router';
import { operationManager } from '../../src/services/operations/operationManager';
import { documentsService } from '../../src/features/documents/documentsService';
import type { DocumentResult } from '../../src/features/documents/documentTypes';
afterEach(() => {
  cleanup();
  operationManager.logout();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
it('logs in, retains a pending document across navigation, and clears it on logout', async () => {
  let finish!: (result: DocumentResult) => void;
  vi.spyOn(documentsService, 'runDemo').mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const fetchSpy = vi.spyOn(window, 'fetch');
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <MemoryRouter>
        <AppRoutes />
      </MemoryRouter>
    </ModeProvider>,
  );
  await user.type(screen.getByLabelText('نام کاربری'), 'demo');
  await user.type(screen.getByLabelText('گذرواژه'), 'Hamtayar123!');
  await user.click(screen.getByRole('button', { name: 'ورود به محیط آزمایشی' }));
  await user.click(
    screen.getByRole('link', { name: 'پردازش اسناد سازمانی', exact: true }),
  );
  await user.upload(
    screen.getByLabelText('انتخاب اسناد'),
    new File(['sample'], 'guide.txt'),
  );
  await user.type(
    within(screen.getByRole('article', { name: 'guide.txt' })).getByRole('textbox', {
      name: /^مرکز/,
    }),
    'alpha',
  );
  await user.selectOptions(screen.getByRole('combobox', { name: /نوع سند/ }), 'normal');
  await user.click(screen.getByRole('button', { name: 'پردازش' }));
  expect(screen.getByRole('combobox', { name: 'حالت اجرا' })).toBeDisabled();
  await user.click(screen.getByRole('link', { name: 'پرسش‌وپاسخ', exact: true }));
  finish({
    provenance: 'fixture',
    label: 'نمونه تکمیل شد',
    status: 'completed',
    message: 'sample',
  });
  await user.click(
    screen.getByRole('link', { name: 'پردازش اسناد سازمانی', exact: true }),
  );
  expect(await screen.findByText('نمونه تکمیل شد')).toBeVisible();
  expect(fetchSpy).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'خروج' }));
  await waitFor(() => expect(operationManager.getSnapshot()).toHaveLength(0));
});
