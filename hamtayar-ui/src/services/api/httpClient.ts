import type { DiagnosticErrorKind } from '../../types/operations';

export type HttpClientError = Error & {
  kind: DiagnosticErrorKind;
  statusCode?: number;
};

export type HttpRequestOptions = Omit<RequestInit, 'signal'> & {
  timeoutMs?: number;
  signal?: AbortSignal;
};

function clientError(
  kind: DiagnosticErrorKind,
  message: string,
  statusCode?: number,
): HttpClientError {
  return Object.assign(new Error(message), { kind, statusCode });
}

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function requestJson<T>(
  url: string,
  options: HttpRequestOptions = {},
): Promise<T> {
  const { timeoutMs = 30_000, signal: callerSignal, ...init } = options;
  const controller = new AbortController();
  let timedOut = false;
  let externallyAborted = false;

  const onCallerAbort = () => {
    externallyAborted = true;
    controller.abort(callerSignal?.reason);
  };
  if (callerSignal?.aborted) onCallerAbort();
  else callerSignal?.addEventListener('abort', onCallerAbort, { once: true });

  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(url, {
      ...init,
      credentials: 'omit',
      signal: controller.signal,
    });
    const body = await readResponse(response);
    if (!response.ok) {
      throw clientError(
        'http',
        'The service returned an unsuccessful response.',
        response.status,
      );
    }
    return body as T;
  } catch (error) {
    if ((error as HttpClientError)?.kind) throw error;
    if (timedOut) {
      throw clientError(
        'timeout',
        'The request timed out; the service outcome may be uncertain.',
      );
    }
    if (externallyAborted) {
      throw clientError(
        'aborted',
        'Waiting for the request was stopped; this does not confirm service-side cancellation.',
      );
    }
    throw clientError('network', 'The service could not be reached.');
  } finally {
    window.clearTimeout(timer);
    callerSignal?.removeEventListener('abort', onCallerAbort);
  }
}
