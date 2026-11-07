import { servicesConfig } from '../../config/services';
import { sampleDocumentResult } from '../../fixtures/documents';
import type { OperationMode } from '../../types/operations';
import type { DocumentDraft } from './documentTypes';
export function validateDocumentFile(
  file: File,
  mode: OperationMode,
): string | undefined {
  if (!/\.(pdf|docx|txt|md|markdown)$/i.test(file.name))
    return 'قالب این فایل پشتیبانی نمی‌شود.';
  if (mode === 'api') {
    const c = servicesConfig.hamtayar;
    if (!c.uploadLimitVerified || !c.maxUploadBytes)
      return 'سقف بارگذاری سرویس تأیید نشده است.';
    if (file.size > c.maxUploadBytes) return 'حجم فایل بیش از سقف سرویس است.';
  }
}
export function validateFixedFields(draft: DocumentDraft): string | undefined {
  if (draft.version.length > 128 || !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(draft.version))
    return 'نسخه باید شناسه انگلیسی معتبر (حداکثر ۱۲۸ نویسه) باشد.';
  if (
    draft.processingProfile.length > 64 ||
    !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(draft.processingProfile)
  )
    return 'پروفایل پردازش معتبر نیست.';
}
export const documentsService = {
  async runDemo(_draft: DocumentDraft) {
    void _draft;
    return { ...sampleDocumentResult };
  },
};
