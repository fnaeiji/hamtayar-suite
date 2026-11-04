import { operationManager } from '../../services/operations/operationManager';

const SESSION_KEY = 'hamtayar-demo-ui.session.v1';
const DEMO_USERNAME = 'demo';
const DEMO_PASSWORD = 'Hamtayar123!';
let signedOutInMemory = false;

type StoredSession = { signedIn: true };

export function signIn(username: string, password: string): boolean {
  if (username !== DEMO_USERNAME || password !== DEMO_PASSWORD) return false;
  try {
    const session: StoredSession = { signedIn: true };
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    signedOutInMemory = false;
    return true;
  } catch {
    return false;
  }
}

export function hasDemoSession(): boolean {
  if (signedOutInMemory) return false;
  try {
    const stored: unknown = JSON.parse(
      window.sessionStorage.getItem(SESSION_KEY) ?? 'null',
    );
    return (
      typeof stored === 'object' &&
      stored !== null &&
      'signedIn' in stored &&
      stored.signedIn === true
    );
  } catch {
    return false;
  }
}

export function signOut(): void {
  signedOutInMemory = true;
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Keep this tab signed out even if browser storage is unavailable.
  }
  operationManager.logout();
}
