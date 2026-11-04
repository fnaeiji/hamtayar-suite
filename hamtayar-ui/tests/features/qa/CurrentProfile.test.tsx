import { render, screen, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { QAPage } from '../../../src/features/qa/QAPage';
import { DocumentIngestionPage } from '../../../src/features/documents/DocumentIngestionPage';
import { registeredCenters } from '../../../src/services/metadata/registeredCenters';
import { operationManager } from '../../../src/services/operations/operationManager';
import { documentsService } from '../../../src/features/documents/documentsService';
afterEach(() => {
  cleanup();
  operationManager.logout();
  vi.restoreAllMocks();
});
it('shows exactly two prompt comboboxes with matching classification choices', async () => {
  registeredCenters.add('مرکز الف');
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <QAPage />
    </ModeProvider>,
  );
  const center = screen.getByRole('combobox', { name: 'مرکز' });
  const level = screen.getByRole('combobox', { name: 'سطح دسترسی' });
  expect(screen.queryByLabelText('نوع سند')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('واحد سازمانی')).not.toBeInTheDocument();
  expect(
    within(level)
      .getAllByRole('option')
      .map((o) => o.textContent),
  ).toEqual(['انتخاب کنید', 'عادی', 'محرمانه', 'خیلی محرمانه']);
  await user.selectOptions(center, 'مرکز الف');
  await user.selectOptions(level, 'confidential');
  await user.type(screen.getByLabelText('پرسش شما'), 'سؤال');
  await user.click(screen.getByRole('button', { name: 'پیش‌نمایش پرسش' }));
  await user.click(screen.getByText('جزئیات تست'));
  const preview = await screen.findByText(/"document_type"/);
  expect(preview).toHaveTextContent('confidential');
  expect(preview).toHaveTextContent('مرکز الف');
  expect(preview).not.toHaveTextContent('access_scope');
});
it('adds only successful document centers, deduplicates them, and keeps them after clearing drafts', async () => {
  const user = userEvent.setup();
  vi.spyOn(documentsService, 'runDemo').mockImplementation(async (d) => {
    if (d.file.name === 'fail.txt') throw new Error('failure');
    return {
      provenance: 'fixture',
      label: 'موفق نمایشی',
      status: 'completed',
      message: 'done',
    };
  });
  const docs = render(
    <ModeProvider>
      <DocumentIngestionPage />
    </ModeProvider>,
  );
  await user.upload(screen.getByLabelText('انتخاب اسناد'), [
    new File(['x'], 'one.txt'),
    new File(['x'], 'two.txt'),
    new File(['x'], 'fail.txt'),
  ]);
  const cards = screen.getAllByRole('article');
  for (const [index, card] of cards.entries()) {
    await user.type(
      within(card).getByRole('textbox', { name: /^مرکز/ }),
      index === 2 ? 'مرکز ناموفق' : ' مرکز الف ',
    );
    await user.selectOptions(
      within(card).getByRole('combobox', { name: /نوع سند/ }),
      'normal',
    );
  }
  expect(registeredCenters.get()).toEqual([]);
  await user.click(screen.getByRole('button', { name: 'اجرای نمایش' }));
  await screen.findByText('نمونه این فایل با خطا روبه‌رو شد.');
  expect(registeredCenters.get()).toEqual(['مرکز الف']);
  await user.click(screen.getByRole('button', { name: 'پاک کردن' }));
  docs.unmount();
  render(
    <ModeProvider>
      <QAPage />
    </ModeProvider>,
  );
  expect(
    within(screen.getByRole('combobox', { name: 'مرکز' }))
      .getAllByRole('option')
      .map((o) => o.textContent),
  ).toEqual(['انتخاب کنید', 'مرکز الف']);
  operationManager.logout();
  expect(registeredCenters.get()).toEqual([]);
});
it('shows an empty center list before any successful registration', () => {
  render(
    <ModeProvider>
      <QAPage />
    </ModeProvider>,
  );
  expect(screen.getByText(/هنوز سندی برای هیچ مرکزی ثبت نشده/)).toBeVisible();
  expect(
    within(screen.getByRole('combobox', { name: 'مرکز' })).getAllByRole('option'),
  ).toHaveLength(1);
});
