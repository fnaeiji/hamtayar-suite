import { servicesConfig, type ServicesConfig } from '../../../config/services';
import type {
  DocumentDraft,
  DocumentResult,
} from '../../../features/documents/documentTypes';
import { validateFixedFields } from '../../../features/documents/documentsService';
import { requestJson } from '../httpClient';
type Config = ServicesConfig['hamtayar'];
function fail(kind: 'blocked' | 'invalid_response'): never {
  throw Object.assign(new Error(kind), { kind });
}
function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
export async function ingestDocument(
  draft: DocumentDraft,
  reducedConfirmed: boolean,
  signal?: AbortSignal,
  config: Config = servicesConfig.hamtayar,
): Promise<DocumentResult> {
  if (
    !config.baseUrl ||
    !config.uploadLimitVerified ||
    !config.maxUploadBytes ||
    draft.file.size > config.maxUploadBytes ||
    validateFixedFields(draft)
  )
    fail('blocked');
  if (Object.keys(draft.customMetadata).length && !reducedConfirmed) fail('blocked');
  const form = new FormData();
  form.append('file', draft.file);
  form.append('source_id', draft.sourceId);
  form.append('knowledge_space_id', draft.knowledgeSpaceId);
  form.append('version', draft.version);
  form.append('processing_profile', draft.processingProfile);
  const r = await requestJson<unknown>(
    `${config.baseUrl}/api/v1/document-ingestion/jobs`,
    { method: 'POST', body: form, timeoutMs: config.timeoutMs, signal },
  );
  if (
    !object(r) ||
    r.status !== 'completed' ||
    typeof r.source_id !== 'string' ||
    typeof r.version !== 'string' ||
    !(
      r.chunks_indexed === null ||
      (typeof r.chunks_indexed === 'number' &&
        Number.isSafeInteger(r.chunks_indexed) &&
        r.chunks_indexed >= 0)
    ) ||
    !(r.request_id == null || typeof r.request_id === 'string')
  )
    fail('invalid_response');
  return {
    provenance: 'service',
    label: 'پاسخ واقعی سرویس؛ بدون ثبت متادیتای سفارشی',
    status: 'completed',
    message: 'پردازش سرویس انجام شد.',
    sourceId: r.source_id,
    version: r.version,
    chunksIndexed: r.chunks_indexed as number | null,
    requestId: typeof r.request_id === 'string' ? r.request_id : undefined,
  };
}
export type AnswerResult = {
  status: 'completed' | 'no_evidence';
  answer: string;
  citations: { title: string; sourceId: string; version: string }[];
  requestId?: string;
};
export async function answerQuestion(
  question: string,
  signal?: AbortSignal,
  config: Config = servicesConfig.hamtayar,
): Promise<AnswerResult> {
  question = question.trim();
  if (
    !config.baseUrl ||
    !question ||
    Array.from(question).length > 4096 ||
    question.includes('\0')
  )
    fail('blocked');
  const r = await requestJson<unknown>(`${config.baseUrl}/api/v1/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    timeoutMs: config.timeoutMs,
    signal,
  });
  if (
    !object(r) ||
    !['completed', 'no_evidence'].includes(String(r.status)) ||
    typeof r.answer !== 'string' ||
    typeof r.request_id !== 'string' ||
    !Array.isArray(r.citations)
  )
    fail('invalid_response');
  const citations = r.citations.map((c: unknown) => {
    if (
      !object(c) ||
      typeof c.evidence_id !== 'string' ||
      typeof c.source_id !== 'string' ||
      typeof c.version !== 'string' ||
      typeof c.knowledge_space_id !== 'string'
    )
      fail('invalid_response');
    return { title: c.evidence_id, sourceId: c.source_id, version: c.version };
  });
  return {
    status: r.status as 'completed' | 'no_evidence',
    answer: r.answer,
    citations,
    requestId: r.request_id,
  };
}
// Source verification is not deployment verification. Enable only after documenting all gates.
export function hamtayarReadiness(operation: 'documents' | 'qa') {
  if (operation === 'qa')
    return { ready: false, reason: 'احراز هویت Q&A در نسخه فعلی آماده نیست (401).' };
  if (!servicesConfig.hamtayar.uploadLimitVerified)
    return { ready: false, reason: 'سقف بارگذاری سرویس تأیید نشده است.' };
  return {
    ready: false,
    reason:
      'آدرس، قرارداد نسخه اجراشده، CORS و اجراکننده بارگذاری هنوز در محیط زنده تأیید نشده‌اند.',
  };
}
