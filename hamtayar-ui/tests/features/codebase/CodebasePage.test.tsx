import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { CodebasePage } from '../../../src/features/codebase/CodebasePage';
import { operationManager } from '../../../src/services/operations/operationManager';
afterEach(() => {
  cleanup();
  operationManager.logout();
  vi.restoreAllMocks();
});
it('runs labeled archive fixtures offline and blocks unverified API', async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(window, 'fetch');
  render(
    <ModeProvider>
      <CodebasePage />
    </ModeProvider>,
  );
  await user.upload(
    screen.getByLabelText('آرشیو کد'),
    new File(['sample'], 'project.zip'),
  );
  await user.type(screen.getByLabelText('نام پروژه'), 'sample');
  await user.click(screen.getByRole('button', { name: 'اجرای نمایش کد' }));
  expect(await screen.findByText(/نمایش نمونه پایان یافت/)).toBeVisible();
  expect(spy).not.toHaveBeenCalled();
  await user.selectOptions(screen.getByRole('combobox', { name: 'حالت اجرا' }), 'api');
  expect(screen.getByRole('button', { name: 'پردازش در سرویس' })).toBeDisabled();
  expect(screen.getByText(/CGC/)).toBeVisible();
});
