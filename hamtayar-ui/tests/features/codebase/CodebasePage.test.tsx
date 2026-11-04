import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { CodebasePage } from '../../../src/features/codebase/CodebasePage';
import { parseCodeWorkspaceUrl } from '../../../src/config/codeWorkspace';
afterEach(cleanup);
it('links to the existing local HamtayarDemo rather than running a code fixture', () => {
  render(<CodebasePage />);
  expect(screen.getByRole('link', { name: 'باز کردن همتایار کد ↖' })).toHaveAttribute(
    'href',
    'http://127.0.0.1:5173/',
  );
  expect(
    screen.queryByRole('button', { name: 'اجرای نمایش کد' }),
  ).not.toBeInTheDocument();
});
it('rejects unsafe and nonlocal code UI addresses', () => {
  expect(parseCodeWorkspaceUrl('javascript:alert(1)')).toBeUndefined();
  expect(parseCodeWorkspaceUrl('https://example.org')).toBeUndefined();
  expect(parseCodeWorkspaceUrl('http://localhost:5173')).toBe('http://localhost:5173/');
});
