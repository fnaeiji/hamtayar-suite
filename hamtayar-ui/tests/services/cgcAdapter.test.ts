import { expect, it } from 'vitest';
import { cgcReadiness } from '../../src/services/api/adapters/cgcAdapter';
it('blocks absent verification and nonlocal unauthenticated targets', () => {
  expect(cgcReadiness({ timeoutMs: 100, localTarget: false }).ready).toBe(false);
  expect(
    cgcReadiness({ baseUrl: 'https://example.org', timeoutMs: 100, localTarget: true })
      .ready,
  ).toBe(false);
  expect(
    cgcReadiness({ baseUrl: 'http://localhost:8001', timeoutMs: 100, localTarget: true })
      .ready,
  ).toBe(false);
});
