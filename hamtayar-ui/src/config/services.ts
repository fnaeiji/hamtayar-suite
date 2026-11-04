export type ServiceName = 'hamtayar' | 'cgc';

export type ServiceConfig = {
  baseUrl?: string;
  timeoutMs: number;
};

export type ServicesConfig = {
  hamtayar: ServiceConfig & {
    /** Present only when a positive, operator-verified limit is configured. */
    maxUploadBytes?: number;
    uploadLimitVerified: boolean;
  };
  cgc: ServiceConfig & {
    /** CGC is unauthenticated; only an explicit loopback target is accepted. */
    localTarget: boolean;
  };
};

export type ServiceConfigIssue = {
  service: ServiceName;
  setting: string;
  message: string;
};

const DEFAULT_TIMEOUT_MS = 30_000;

function readTimeout(
  value: string | undefined,
  setting: string,
  issues: ServiceConfigIssue[],
  service: ServiceName,
): number {
  if (value === undefined || value.trim() === '') return DEFAULT_TIMEOUT_MS;
  const parsed = Number(value);
  if (Number.isSafeInteger(parsed) && parsed > 0) return parsed;
  issues.push({
    service,
    setting,
    message: 'Timeout must be a positive whole number of milliseconds.',
  });
  return DEFAULT_TIMEOUT_MS;
}

function readBaseUrl(
  value: string | undefined,
  setting: string,
  issues: ServiceConfigIssue[],
  service: ServiceName,
): string | undefined {
  if (value === undefined || value.trim() === '') return undefined;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') throw new Error();
    if (parsed.username || parsed.password) throw new Error();
    return parsed.toString().replace(/\/$/, '');
  } catch {
    issues.push({
      service,
      setting,
      message: 'Enter a valid HTTP(S) URL without embedded credentials.',
    });
    return undefined;
  }
}

function isLoopback(url: string | undefined): boolean {
  if (!url) return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return (
      hostname === 'localhost' ||
      hostname === '::1' ||
      hostname === '[::1]' ||
      /^127(?:\.\d{1,3}){3}$/.test(hostname)
    );
  } catch {
    return false;
  }
}

export function parseServicesConfig(env: Record<string, string | undefined>): {
  config: ServicesConfig;
  issues: ServiceConfigIssue[];
} {
  const issues: ServiceConfigIssue[] = [];
  const hamtayarUrl = readBaseUrl(
    env.VITE_HAMTAYAR_BASE_URL,
    'VITE_HAMTAYAR_BASE_URL',
    issues,
    'hamtayar',
  );
  const cgcUrl = readBaseUrl(env.VITE_CGC_BASE_URL, 'VITE_CGC_BASE_URL', issues, 'cgc');
  if (cgcUrl && !isLoopback(cgcUrl)) {
    issues.push({
      service: 'cgc',
      setting: 'VITE_CGC_BASE_URL',
      message:
        'CGC is unauthenticated and must use an explicitly configured loopback target.',
    });
  }
  const uploadText = env.VITE_HAMTAYAR_MAX_UPLOAD_BYTES?.trim();
  let maxUploadBytes: number | undefined;
  if (uploadText) {
    const parsed = Number(uploadText);
    if (Number.isSafeInteger(parsed) && parsed > 0) maxUploadBytes = parsed;
    else {
      issues.push({
        service: 'hamtayar',
        setting: 'VITE_HAMTAYAR_MAX_UPLOAD_BYTES',
        message: 'Upload limit must be a positive whole number of bytes.',
      });
    }
  }
  const uploadLimitVerified =
    maxUploadBytes !== undefined &&
    env.VITE_HAMTAYAR_MAX_UPLOAD_BYTES_VERIFIED?.toLowerCase() === 'true';
  if (maxUploadBytes !== undefined && !uploadLimitVerified) {
    issues.push({
      service: 'hamtayar',
      setting: 'VITE_HAMTAYAR_MAX_UPLOAD_BYTES_VERIFIED',
      message:
        'Confirm the upload limit against the configured service before enabling uploads.',
    });
  }

  const config: ServicesConfig = {
    hamtayar: {
      baseUrl: hamtayarUrl,
      timeoutMs: readTimeout(
        env.VITE_HAMTAYAR_TIMEOUT_MS,
        'VITE_HAMTAYAR_TIMEOUT_MS',
        issues,
        'hamtayar',
      ),
      maxUploadBytes,
      uploadLimitVerified,
    },
    cgc: {
      baseUrl: cgcUrl,
      timeoutMs: readTimeout(
        env.VITE_CGC_TIMEOUT_MS,
        'VITE_CGC_TIMEOUT_MS',
        issues,
        'cgc',
      ),
      localTarget: isLoopback(cgcUrl),
    },
  };
  return { config, issues };
}

const parsedConfig = parseServicesConfig(import.meta.env);
export const servicesConfig = parsedConfig.config;
export const servicesConfigIssues = parsedConfig.issues;
