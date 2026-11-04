import { servicesConfig, type ServicesConfig } from '../../../config/services';
export function cgcReadiness(config: ServicesConfig['cgc'] = servicesConfig.cgc) {
  let local = false;
  try {
    const u = new URL(config.baseUrl ?? '');
    local =
      ['localhost', '127.0.0.1', '[::1]'].includes(u.hostname) &&
      ['http:', 'https:'].includes(u.protocol) &&
      !u.username &&
      !u.password;
  } catch {
    /* Missing configuration remains blocked. */
  }
  return {
    ready: false,
    reason: !local
      ? 'CGC فقط با آدرس محلی صریح قابل بررسی است.'
      : 'CGC: قرارداد زنده، سقف آرشیو، ابزار CGC، دو Neo4j و CORS تأیید نشده‌اند.',
  };
}
