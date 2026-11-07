import { useSyncExternalStore } from 'react';
import type { OperationMode, SanitizedDiagnostic } from '../../types/operations';
import type { HttpClientError } from '../api/httpClient';
import { operationManager } from './operationManager';

export function useOperation<T>(id: string) {
  return useSyncExternalStore(operationManager.subscribe, () =>
    operationManager.get<T>(id),
  );
}
export function diagnose(error: unknown): SanitizedDiagnostic {
  const e = error as Partial<HttpClientError>;
  const messages: Record<number, string> = {
    401: 'احراز هویت سرویس آماده نیست.',
    422: 'سرویس ورودی را نپذیرفت.',
    413: 'حجم فایل بیش از سقف سرویس است.',
    429: 'تعداد درخواست‌ها بیش از سقف سرویس است؛ بعداً دوباره امتحان کنید.',
    500: 'خطای داخلی سرویس.',
    503: 'اجراکننده سرویس آماده نیست.',
    504: 'مهلت سرویس تمام شد؛ نتیجه بارگذاری نامشخص است.',
  };
  const kind = e?.kind ?? 'invalid_response';
  return {
    kind,
    statusCode: e?.statusCode,
    message: e?.statusCode
      ? (messages[e.statusCode] ?? 'درخواست توسط سرویس رد شد.')
      : {
          timeout: 'مهلت انتظار تمام شد؛ پردازش سرویس ممکن است ادامه داشته باشد.',
          network: 'ارتباط با سرویس برقرار نشد؛ نتیجه بارگذاری نامشخص است.',
          aborted: 'انتظار متوقف شد؛ لغو پردازش سرویس تأیید نشده است.',
          blocked: 'عملیات تا تأیید آمادگی سرویس مسدود است.',
          invalid_response: 'پاسخ سرویس معتبر نیست.',
          http: 'خطای سرویس.',
        }[kind],
  };
}
export async function runOperation<T>(
  id: string,
  mode: OperationMode,
  work: (signal: AbortSignal) => Promise<T>,
  upload = false,
) {
  if (operationManager.get(id)?.status === 'pending') return;
  const record = operationManager.begin(id, mode);
  const controller = new AbortController();
  const unregister = operationManager.registerCleanup(id, () => controller.abort());
  operationManager.update(id, record.generation, { status: 'pending' });
  try {
    const result = await work(controller.signal);
    const accepted = operationManager.update(id, record.generation, {
      status: 'completed',
      result,
      provenance: mode === 'demo' ? 'fixture' : 'service',
    });
    if (accepted) return result;
  } catch (error) {
    const diagnostic = diagnose(error);
    const uncertain =
      mode === 'api' &&
      upload &&
      (['timeout', 'network', 'aborted', 'invalid_response'].includes(diagnostic.kind) ||
        diagnostic.statusCode === 504);
    operationManager.update(id, record.generation, {
      status: uncertain ? 'uncertain' : 'failed',
      diagnostic,
    });
  } finally {
    unregister();
  }
}
