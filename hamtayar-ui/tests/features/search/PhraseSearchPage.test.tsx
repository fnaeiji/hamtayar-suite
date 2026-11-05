import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { PhraseSearchPage } from '../../../src/features/search/PhraseSearchPage';
import { documentCatalog } from '../../../src/services/documentCatalog';
import { operationManager } from '../../../src/services/operations/operationManager';
import { searchDocuments } from '../../../src/features/search/searchDocuments';
afterEach(() => {
  cleanup();
  operationManager.logout();
  vi.restoreAllMocks();
});
it('searches literal phrases and applies center/classification together without operational requests', async () => {
  documentCatalog.register({
    sourceId: 'a',
    name: 'a.txt',
    center: 'الف',
    classification: 'normal',
    text: 'مدیریت دانش در سازمان مهم است.',
  });
  documentCatalog.register({
    sourceId: 'b',
    name: 'b.txt',
    center: 'ب',
    classification: 'confidential',
    text: 'مدیریت دانش برای تیم محرمانه',
  });
  documentCatalog.register({
    sourceId: 'c',
    name: 'c.pdf',
    center: 'الف',
    classification: 'normal',
    searchNote: 'PDF is not parsed locally.',
  });
  const fetch = vi.spyOn(window, 'fetch');
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <PhraseSearchPage />
    </ModeProvider>,
  );
  await user.type(screen.getByLabelText('عبارت موردنظر'), 'مدیریت دانش');
  await user.selectOptions(screen.getByLabelText('مرکز'), 'الف');
  await user.selectOptions(screen.getByLabelText('نوع سند'), 'normal');
  await user.click(screen.getByRole('button', { name: 'جستجوی عبارت' }));
  expect(await screen.findByRole('heading', { name: 'a.txt' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'b.txt' })).not.toBeInTheDocument();
  expect(screen.getByText('مدیریت دانش', { selector: 'mark' })).toBeVisible();
  expect(screen.getByText(/سند در جستجوی محلی پوشش ندارد/)).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
});
it('treats regex metacharacters literally and does not invent matches', () => {
  const docs = [
    {
      sourceId: 'a',
      name: 'a.txt',
      center: 'الف',
      classification: 'normal',
      text: 'Literal [x]. ASP.NET',
    },
  ];
  expect(searchDocuments(docs, '[x].', '', '')).toHaveLength(1);
  expect(searchDocuments(docs, 'asp.net', '', '')).toHaveLength(1);
  expect(searchDocuments(docs, '.*', '', '')).toHaveLength(0);
});
