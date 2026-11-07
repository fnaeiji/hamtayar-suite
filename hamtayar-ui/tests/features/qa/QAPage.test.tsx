import { ModeSelector } from '../../../src/components/common/ModeSelector';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { QAPage } from '../../../src/features/qa/QAPage';
import { buildQuery } from '../../../src/features/qa/queryModel';
import { questionMetadataDefinitions } from '../../../src/config/demoProfile';
import { operationManager } from '../../../src/services/operations/operationManager';
afterEach(() => {
  cleanup();
  operationManager.logout();
  vi.restoreAllMocks();
});
it('builds current metadata with AND equality and omits empty and obsolete fields', () => {
  const query = buildQuery(
    ' test ',
    { person_access_level: 'confidential' },
    { center: 'الف', document_type: 'normal', department: 'obsolete' },
    questionMetadataDefinitions(['الف']),
  );
  expect(query).toEqual({
    question: 'test',
    user_metadata: { person_access_level: 'confidential' },
    filters: {
      operator: 'and',
      conditions: [
        { key: 'center', operator: 'eq', value: 'الف' },
        { key: 'document_type', operator: 'eq', value: 'normal' },
      ],
    },
  });
  expect(
    buildQuery('test', {}, {}, questionMetadataDefinitions([])).filters.conditions,
  ).toEqual([]);
});
it('shows sample sources without requests and discloses question-only API boundary', async () => {
  const fetchSpy = vi.spyOn(window, 'fetch');
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <ModeSelector />
      <QAPage />
    </ModeProvider>,
  );
  await user.type(screen.getByLabelText('پرسش شما'), 'همتایار چیست؟');
  await user.click(screen.getByRole('button', { name: 'پاسخ' }));
  expect(await screen.findByText('راهنمای نمونه همتایار')).toBeVisible();
  expect(fetchSpy).not.toHaveBeenCalled();
  await user.selectOptions(screen.getByRole('combobox', { name: 'حالت اجرا' }), 'api');
  expect(screen.getByText(/فقط سؤال ارسال می‌شود/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'پاسخ' })).toBeDisabled();
});
it('retains question input when fixture processing fails', async () => {
  const { qaService } = await import('../../../src/features/qa/qaService');
  vi.spyOn(qaService, 'runDemo').mockRejectedValue(new Error('private stack'));
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <ModeSelector />
      <QAPage />
    </ModeProvider>,
  );
  await user.type(screen.getByLabelText('پرسش شما'), 'keep this question');
  await user.click(screen.getByRole('button', { name: 'پاسخ' }));
  expect(await screen.findByRole('alert')).not.toHaveTextContent('private stack');
  expect(screen.getByLabelText('پرسش شما')).toHaveValue('keep this question');
});
