import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { SafeAnswerMarkdown } from '../../src/components/answers/SafeAnswerMarkdown';
afterEach(cleanup);
it('renders Markdown without executable HTML or unsafe URLs', () => {
  const { container } = render(
    <SafeAnswerMarkdown
      text={
        '**پاسخ** <script>alert(1)</script>\n\n[unsafe](javascript:alert%281%29)\n\n[docs](https://example.org)'
      }
    />,
  );
  expect(container.querySelector('script')).toBeNull();
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  expect(screen.getByText('پاسخ').tagName).toBe('STRONG');
});
