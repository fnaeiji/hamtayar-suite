export type ServicesConfig = {
  hamtayar: {
    baseUrl?: string;
    timeoutMs: number;
    maxUploadBytes?: number;
    uploadLimitVerified: boolean;
  };
};
function positiveInteger(value: string | undefined): number | undefined {
  if (!value?.trim()) return undefined;
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : undefined;
}
function serviceUrl(value: string | undefined): string | undefined {
  if (!value?.trim()) return undefined;
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password)
      return undefined;
    return url.toString().replace(/\/$/, '');
  } catch {
    return undefined;
  }
}
const env = import.meta.env;
const maxUploadBytes = positiveInteger(env.VITE_HAMTAYAR_MAX_UPLOAD_BYTES);
export const servicesConfig: ServicesConfig = {
  hamtayar: {
    baseUrl: serviceUrl(env.VITE_HAMTAYAR_BASE_URL),
    timeoutMs: positiveInteger(env.VITE_HAMTAYAR_TIMEOUT_MS) ?? 30000,
    maxUploadBytes,
    uploadLimitVerified:
      maxUploadBytes !== undefined &&
      env.VITE_HAMTAYAR_MAX_UPLOAD_BYTES_VERIFIED?.toLowerCase() === 'true',
  },
};
