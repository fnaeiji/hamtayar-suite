import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { TestDetailsPanel } from '../../src/components/operations/TestDetailsPanel';
afterEach(cleanup);
it('separates intended and transmitted values and strips sensitive fields', async () => {
  const { container } = render(
    <TestDetailsPanel
      intended={{
        question: 'test',
        token: 'secret-token',
        nested: { password: 'secret-password', stack: 'trace' },
      }}
      transmitted={{ question: 'test' }}
    />,
  );
  const details = container.querySelector('details')!;
  details.open = true;
  fireEvent(details, new Event('toggle'));
  const pre = await screen.findByText(/"intended"/);
  expect(pre).toHaveTextContent('transmitted');
  expect(pre).not.toHaveTextContent('secret-token');
  expect(pre).not.toHaveTextContent('secret-password');
  expect(pre).not.toHaveTextContent('requestId');
});
