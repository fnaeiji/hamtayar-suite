export function parseCodeWorkspaceUrl(value: string | undefined): string | undefined {
  try {
    const url = new URL(value?.trim() || 'http://127.0.0.1:5173');
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    )
      return undefined;
    return url.href;
  } catch {
    return undefined;
  }
}
export const codeWorkspaceUrl = parseCodeWorkspaceUrl(import.meta.env.VITE_CGC_UI_URL);
