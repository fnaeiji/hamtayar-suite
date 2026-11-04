import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { MetadataSettingsPage } from '../../../src/features/metadata/MetadataSettingsPage';
import { metadataConfigService } from '../../../src/services/metadata/metadataConfigService';

function renderPage() {
  return render(
    <MemoryRouter>
      <MetadataSettingsPage />
    </MemoryRouter>,
  );
}

describe('metadata settings page', () => {
  beforeEach(() => {
    window.localStorage.clear();
    metadataConfigService.restoreDefaults();
  });

  afterEach(() => {
    cleanup();
    metadataConfigService.clearDraftValues();
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it('explains that definitions are local and supports adding/editing/removing a field', async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText(/فقط در همین مرورگر/)).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'افزودن فیلد' }));
    await user.type(screen.getByLabelText('کلید انگلیسی'), 'retention_period');
    await user.type(screen.getByLabelText('برچسب فارسی'), 'مدت نگهداری');
    await user.click(screen.getByRole('button', { name: 'ذخیره فیلد' }));

    expect(await screen.findByRole('heading', { name: 'مدت نگهداری' })).toBeVisible();
    expect(screen.getByLabelText('مدت نگهداری')).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'ویرایش مدت نگهداری' }));
    await user.clear(screen.getByLabelText('برچسب فارسی'));
    await user.type(screen.getByLabelText('برچسب فارسی'), 'دوره نگهداری');
    await user.click(screen.getByRole('button', { name: 'ذخیره فیلد' }));
    expect(await screen.findByRole('heading', { name: 'دوره نگهداری' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'حذف دوره نگهداری' }));
    expect(screen.queryByRole('heading', { name: 'دوره نگهداری' })).not.toBeInTheDocument();
  });

  it('rejects invalid definitions with a visible Persian message', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/فقط در همین مرورگر/);
    await user.click(screen.getByRole('button', { name: 'افزودن فیلد' }));
    await user.type(screen.getByLabelText('کلید انگلیسی'), 'tenant_id');
    await user.type(screen.getByLabelText('برچسب فارسی'), 'شناسه');
    await user.click(screen.getByRole('button', { name: 'ذخیره فیلد' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/کلید رزروشده/);
    expect(screen.queryByRole('heading', { name: 'شناسه' })).not.toBeInTheDocument();
  });

  it('confirms before discarding a value and lets the operator cancel deletion', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();
    await screen.findByLabelText('پروژه');
    await user.type(screen.getByLabelText('پروژه'), 'demo value');
    await user.click(screen.getByRole('button', { name: 'حذف پروژه' }));

    expect(confirm).toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'پروژه' })).toBeVisible();
  });

  it('reflects changed definitions in the dynamic form preview', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/فقط در همین مرورگر/);
    await user.click(screen.getByRole('button', { name: 'افزودن فیلد' }));
    await user.type(screen.getByLabelText('کلید انگلیسی'), 'review_status');
    await user.type(screen.getByLabelText('برچسب فارسی'), 'وضعیت بررسی');
    await user.selectOptions(screen.getByLabelText('گروه'), 'document');
    await user.selectOptions(screen.getByLabelText('نوع داده'), 'select');
    await user.type(screen.getByLabelText('گزینه‌ها (هر خط: مقدار=برچسب فارسی)'), 'approved=تأییدشده');
    await user.click(screen.getByRole('button', { name: 'ذخیره فیلد' }));

    await waitFor(() => expect(screen.getByLabelText('وضعیت بررسی')).toBeVisible());
  });

  it('derives Q&A filters from filterable document fields', async () => {
    renderPage();
    await screen.findByText(/فقط در همین مرورگر/);
    const filterPreview = screen.getByRole('region', {
      name: 'پیش‌نمایش فیلترهای پرسش‌وپاسخ',
    });
    expect(within(filterPreview).getByLabelText('واحد سازمانی')).toBeVisible();
    expect(within(filterPreview).getByLabelText('نوع سند')).toBeVisible();
    expect(within(filterPreview).queryByLabelText('پروژه')).not.toBeInTheDocument();
  });

  it('offers restore defaults with a discard confirmation', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    await screen.findByText(/فقط در همین مرورگر/);
    await user.click(screen.getByRole('button', { name: 'افزودن فیلد' }));
    await user.type(screen.getByLabelText('کلید انگلیسی'), 'temporary_note');
    await user.type(screen.getByLabelText('برچسب فارسی'), 'یادداشت موقت');
    await user.click(screen.getByRole('button', { name: 'ذخیره فیلد' }));
    await user.type(await screen.findByLabelText('یادداشت موقت'), 'مقدار آزمایشی');
    await user.click(screen.getByRole('button', { name: 'بازگردانی پیش‌فرض‌ها' }));
    expect(confirm).toHaveBeenCalled();
    await waitFor(() => expect(metadataConfigService.getSnapshot().definitions).toHaveLength(7));
  });
});
