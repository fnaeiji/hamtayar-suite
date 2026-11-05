import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { QAPage } from '../../../src/features/qa/QAPage';
import { buildQuery } from '../../../src/features/qa/queryModel';
import { DEMO_METADATA_FIELDS } from '../../../src/config/demoProfile';
import { operationManager } from '../../../src/services/operations/operationManager';
afterEach(() => {
  cleanup();
  operationManager.logout();
  vi.restoreAllMocks();
});
it('converts filters to equality/any-of under AND and retains zero/false', () => {
  const definitions = [
    ...DEMO_METADATA_FIELDS,
    {
      key: 'count',
      labelFa: 'تعداد',
      group: 'document' as const,
      type: 'number' as const,
      filterable: true,
      enabled: true,
      visibleInForm: true,
      required: true,
    },
    {
      key: 'active',
      labelFa: 'فعال',
      group: 'document' as const,
      type: 'boolean' as const,
      filterable: true,
      enabled: true,
      visibleInForm: true,
      required: true,
    },
  ];
  const query = buildQuery(
    ' test ',
    {},
    {
      department: 'engineering',
      tags: ['internal', 'research'],
      count: 0,
      active: false,
      project: '',
    },
    definitions,
  );
  expect(query.question).toBe('test');
  expect(query.filters.operator).toBe('and');
  expect(query.filters.conditions).toEqual(
    expect.arrayContaining([
      { key: 'count', operator: 'eq', value: 0 },
      { key: 'active', operator: 'eq', value: false },
    ]),
  );
  expect(query.filters.conditions.some((c) => c.key === 'project')).toBe(false);
});
it('shows sample sources without requests and discloses question-only API boundary', async () => {
  const fetchSpy = vi.spyOn(window, 'fetch');
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <QAPage />
    </ModeProvider>,
  );
  await user.type(screen.getByLabelText('پرسش شما'), 'همتایار چیست؟');
  await user.click(screen.getByRole('button', { name: 'نمایش پاسخ نمونه' }));
  expect(await screen.findByText('راهنمای نمونه همتایار')).toBeVisible();
  expect(fetchSpy).not.toHaveBeenCalled();
  await user.selectOptions(screen.getByRole('combobox', { name: 'حالت اجرا' }), 'api');
  expect(screen.getByText(/فقط سؤال ارسال می‌شود/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'آزمون فقط سؤال' })).toBeDisabled();
});
it('retains question input when fixture processing fails', async () => {
  const { qaService } = await import('../../../src/features/qa/qaService');
  vi.spyOn(qaService, 'runDemo').mockRejectedValue(new Error('private stack'));
  const user = userEvent.setup();
  render(
    <ModeProvider>
      <QAPage />
    </ModeProvider>,
  );
  await user.type(screen.getByLabelText('پرسش شما'), 'keep this question');
  await user.click(screen.getByRole('button', { name: 'نمایش پاسخ نمونه' }));
  expect(await screen.findByRole('alert')).not.toHaveTextContent('private stack');
  expect(screen.getByLabelText('پرسش شما')).toHaveValue('keep this question');
});
