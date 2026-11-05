// @vitest-environment node
import { expect, it } from 'vitest';
import { codeApiTarget } from '../../vite.config';
it('accepts only explicit local backend origins without exposing unauthenticated CGC remotely', () => {
  expect(codeApiTarget(undefined)).toBe('http://127.0.0.1:8000');
  expect(() => codeApiTarget('https://example.org')).toThrow();
  expect(() => codeApiTarget('http://user:password@localhost:8000')).toThrow();
  expect(() => codeApiTarget('http://localhost:8000/another-path')).toThrow();
});
