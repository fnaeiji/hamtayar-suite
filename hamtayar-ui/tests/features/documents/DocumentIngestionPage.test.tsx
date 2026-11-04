import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { DocumentIngestionPage } from '../../../src/features/documents/DocumentIngestionPage';
import { documentsService } from '../../../src/features/documents/documentsService';
import { operationManager } from '../../../src/services/operations/operationManager';

function file(name = 'handbook.pdf', size = 12, type = 'application/pdf') {
  return new File([new Uint8Array(size)], name, { type });
}

function renderPage() {
  return render(
    <ModeProvider>
      <MemoryRouter>
        <DocumentIngestionPage />
      </MemoryRouter>
    </ModeProvider>,
  );
}

describe('document ingestion Demo flow', () => {
  beforeEach(() => {
    window.localStorage.clear();
    operationManager.logout();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it('uses the same file-type validation for selection and drag/drop and shows file facts', async () => {
    const user = userEvent.setup();
    renderPage();
    const picker = await screen.findByLabelText('انتخاب اسناد');
    await user.upload(picker, file('guide.pdf', 25));
    expect(await screen.findByText('guide.pdf')).toBeVisible();
    expect(screen.getByText(/25 بایت/)).toBeVisible();

    const dropZone = screen.getByRole('region', { name: 'انتخاب یا رها کردن اسناد' });
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file('bad.exe', 10, 'application/octet-stream')] },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /قالب این فایل پشتیبانی نمی‌شود/,
    );
    expect(screen.queryByText('bad.exe')).not.toBeInTheDocument();
  });

  it('accepts multiple files without an artificial Demo size cap', async () => {
    const user = userEvent.setup();
    renderPage();
    const picker = await screen.findByLabelText('انتخاب اسناد');
    await user.upload(picker, [
      file('large.txt', 3_000_000, 'text/plain'),
      file('notes.md'),
    ]);

    expect(await screen.findByText('large.txt')).toBeVisible();
    expect(screen.getByText('notes.md')).toBeVisible();
  });

  it('supports per-file fixed metadata and shared custom values with per-file overrides', async () => {
    const user = userEvent.setup();
    renderPage();
    const picker = await screen.findByLabelText('انتخاب اسناد');
    await user.upload(picker, [file('one.pdf'), file('two.pdf')]);
    await user.type(screen.getByLabelText('فضای دانشی مشترک'), 'team-docs');
    await user.type(screen.getByLabelText('پروژه مشترک'), 'alpha');

    const firstCard = screen.getByRole('article', { name: 'one.pdf' });
    const secondCard = screen.getByRole('article', { name: 'two.pdf' });
    expect(within(firstCard).getByLabelText('شناسه منبع')).toHaveProperty(
      'value',
      expect.stringMatching(/.+/),
    );
    expect(within(firstCard).getByLabelText('فضای دانشی')).toHaveValue('team-docs');
    expect(within(secondCard).getByLabelText('پروژه')).toHaveValue('alpha');

    await user.clear(within(secondCard).getByLabelText('پروژه'));
    await user.type(within(secondCard).getByLabelText('پروژه'), 'beta');
    expect(within(firstCard).getByLabelText('پروژه')).toHaveValue('alpha');
    expect(within(secondCard).getByLabelText('پروژه')).toHaveValue('beta');
  });

  it('previews and clears intended request data', async () => {
    const user = userEvent.setup();
    renderPage();
    const picker = await screen.findByLabelText('انتخاب اسناد');
    await user.upload(picker, file());
    await user.type(screen.getByLabelText('فضای دانشی مشترک'), 'manuals');
    await user.click(screen.getByRole('button', { name: 'پیش‌نمایش درخواست' }));

    expect(
      await screen.findByRole('region', { name: 'پیش‌نمایش درخواست‌ها' }),
    ).toHaveTextContent('manuals');
    await user.click(screen.getByRole('button', { name: 'پاک کردن' }));
    expect(screen.queryByText('handbook.pdf')).not.toBeInTheDocument();
  });

  it('keeps per-file outcomes independent when one Demo operation fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(documentsService, 'runDemo').mockImplementation(async (draft) => {
      if (draft.file.name === 'bad.txt') throw new Error('sample failure');
      return {
        provenance: 'fixture',
        label: 'نتیجه نمایشی؛ داده در بک‌اند ثبت نمی‌شود',
        status: 'completed',
        message: 'پردازش نمونه انجام شد.',
      };
    });
    renderPage();
    const picker = await screen.findByLabelText('انتخاب اسناد');
    await user.upload(picker, [file('good.pdf'), file('bad.txt', 12, 'text/plain')]);
    await user.type(screen.getByLabelText('فضای دانشی مشترک'), 'team-docs');
    await user.click(screen.getByRole('button', { name: 'اجرای نمایش' }));

    expect(await screen.findByText(/نتیجه نمایشی/)).toBeVisible();
    expect(screen.getByText(/نمونه این فایل با خطا روبه‌رو شد/)).toBeVisible();
    expect(screen.getByRole('article', { name: 'good.pdf' })).toHaveTextContent(
      'completed',
    );
    expect(screen.getByRole('article', { name: 'bad.txt' })).toHaveTextContent('failed');
  });

  it('blocks API upload while its verified service limit is unknown', async () => {
    const user = userEvent.setup();
    renderPage();
    const mode = await screen.findByRole('combobox', { name: 'حالت اجرا' });
    await user.selectOptions(mode, 'api');
    const picker = screen.getByLabelText('انتخاب اسناد');
    await user.upload(picker, file());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /سقف بارگذاری سرویس تأیید نشده است/,
    );
    expect(screen.getByRole('button', { name: 'ارسال به سرویس' })).toBeDisabled();
  });

  it('makes no operational request in Demo mode', async () => {
    const fetchSpy = vi.spyOn(window, 'fetch');
    const user = userEvent.setup();
    renderPage();
    const picker = await screen.findByLabelText('انتخاب اسناد');
    await user.upload(picker, file());
    await user.type(screen.getByLabelText('فضای دانشی مشترک'), 'team-docs');
    await user.click(screen.getByRole('button', { name: 'اجرای نمایش' }));

    await waitFor(() => expect(screen.getByText(/نتیجه نمایشی/)).toBeVisible());
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
