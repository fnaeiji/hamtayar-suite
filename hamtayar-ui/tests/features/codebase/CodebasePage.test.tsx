import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { CodebasePage } from '../../../src/features/codebase/CodebasePage';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('hosts the original code workspace on the same origin and sends only a page command', () => {
  render(
    <MemoryRouter initialEntries={['/codebase/graph']}>
      <Routes>
        <Route path="/codebase/:view" element={<CodebasePage />} />
      </Routes>
    </MemoryRouter>,
  );
  const frame = screen.getByTitle('همتایار کد — پردازش کدبیس') as HTMLIFrameElement;
  expect(frame).toHaveAttribute('src', '/code/index.html?embedded=1');
  const send = vi.spyOn(frame.contentWindow!, 'postMessage');
  fireEvent.load(frame);
  expect(send).toHaveBeenCalledWith(
    { type: 'hamtayar:code:navigate', page: 'graph' },
    window.location.origin,
  );
  fireEvent(
    window,
    new MessageEvent('message', {
      origin: 'https://example.org',
      source: frame.contentWindow,
      data: { type: 'hamtayar:code:page', page: 'settings' },
    }),
  );
  expect(screen.getByText(/کاوش گراف/)).toBeVisible();
});
