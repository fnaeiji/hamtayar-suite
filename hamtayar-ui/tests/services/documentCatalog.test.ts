import { afterEach, expect, it } from 'vitest';
import {
  documentCatalog,
  prepareLocalDocument,
} from '../../src/services/documentCatalog';
import { operationManager } from '../../src/services/operations/operationManager';
import type { DocumentDraft } from '../../src/features/documents/documentTypes';
afterEach(() => operationManager.logout());
function draft(file: File): DocumentDraft {
  return {
    id: 'draft',
    sourceId: 'source',
    file,
    knowledgeSpaceId: 'demo-documents',
    version: '1',
    processingProfile: 'default',
    customMetadata: { center: ' مرکز الف ', document_type: 'normal' },
  };
}
it('reads actual UTF-8 text and replaces an explicit retry by source identity', async () => {
  const local = await prepareLocalDocument(
    draft(new File(['مدیریت دانش'], 'a.txt')),
    new AbortController().signal,
  );
  expect(local.text).toBe('مدیریت دانش');
  documentCatalog.register(local);
  documentCatalog.register({ ...local, center: 'مرکز ب' });
  expect(documentCatalog.get().documents).toHaveLength(1);
  expect(documentCatalog.get().centers).toEqual(['مرکز ب']);
  operationManager.clearTransient();
  expect(documentCatalog.get().documents).toHaveLength(0);
});
it('discloses unsupported formats and bounded local text indexing without blocking registration', async () => {
  const signal = new AbortController().signal;
  expect(
    (await prepareLocalDocument(draft(new File(['pdf'], 'a.pdf')), signal)).searchNote,
  ).toMatch(/TXT/);
  const large = await prepareLocalDocument(
    draft(new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'large.txt')),
    signal,
  );
  expect(large.text).toBeUndefined();
  expect(large.searchNote).toMatch(/۲ مگابایت/);
  const invalid = await prepareLocalDocument(
    draft(new File([new Uint8Array([255])], 'invalid.txt')),
    signal,
  );
  expect(invalid.text).toBeUndefined();
  expect(invalid.searchNote).toMatch(/UTF-8/);
});
it('stops local reading for an already-aborted session', async () => {
  const controller = new AbortController();
  controller.abort();
  await expect(
    prepareLocalDocument(draft(new File(['data'], 'a.txt')), controller.signal),
  ).rejects.toMatchObject({ name: 'AbortError' });
});
