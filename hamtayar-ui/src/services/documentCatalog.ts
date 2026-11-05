import { createWorkspaceStore } from './operations/workspaceStore';
import type { DocumentDraft } from '../features/documents/documentTypes';
export type LocalDocument = {
  sourceId: string;
  name: string;
  center: string;
  classification: string;
  text?: string;
  searchNote?: string;
};
const store = createWorkspaceStore(() => ({
  documents: [] as LocalDocument[],
  centers: [] as string[],
}));
export const documentCatalog = {
  use: store.use,
  get: store.get,
  register(document: LocalDocument) {
    const center = document.center.trim().replace(/\s+/g, ' ');
    if (!center) return;
    const documents = [
      ...store.get().documents.filter((d) => d.sourceId !== document.sourceId),
      { ...document, center },
    ];
    store.set({ documents, centers: [...new Set(documents.map((d) => d.center))] });
  },
};
const LOCAL_TEXT_LIMIT = 2 * 1024 * 1024;
/** A bounded local text copy for the search Demo. It is not a backend index. */
export async function prepareLocalDocument(
  draft: DocumentDraft,
  signal: AbortSignal,
): Promise<LocalDocument> {
  const document: LocalDocument = {
    sourceId: draft.sourceId,
    name: draft.file.name,
    center: String(draft.customMetadata.center ?? ''),
    classification: String(draft.customMetadata.document_type ?? ''),
  };
  if (!/\.(txt|md|markdown)$/i.test(draft.file.name))
    return { ...document, searchNote: 'جستجوی محلی فقط برای TXT و Markdown آماده است.' };
  if (draft.file.size > LOCAL_TEXT_LIMIT)
    return {
      ...document,
      searchNote: 'فایل ثبت شد؛ جستجوی محلی برای متن‌های حداکثر ۲ مگابایت است.',
    };
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    const finish = () => signal.removeEventListener('abort', abort);
    const abort = () => {
      reader.abort();
      finish();
      reject(new DOMException('Stopped waiting', 'AbortError'));
    };
    reader.onload = () => {
      finish();
      try {
        resolve({
          ...document,
          text: new TextDecoder('utf-8', { fatal: true }).decode(
            reader.result as ArrayBuffer,
          ),
        });
      } catch {
        resolve({
          ...document,
          searchNote: 'متن فایل UTF-8 معتبر نیست؛ جستجوی محلی انجام نمی‌شود.',
        });
      }
    };
    reader.onerror = () => {
      finish();
      resolve({ ...document, searchNote: 'متن فایل برای جستجوی محلی خوانده نشد.' });
    };
    if (signal.aborted) {
      abort();
      return;
    }
    signal.addEventListener('abort', abort, { once: true });
    reader.readAsArrayBuffer(draft.file);
  });
}
