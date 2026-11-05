import { useSyncExternalStore } from 'react';
import { operationManager } from './operationManager';

/** Memory only: survives route changes, never browser reload or logout. */
export function createWorkspaceStore<T>(initial: () => T) {
  let state = initial();
  const listeners = new Set<() => void>();
  const set = (update: Partial<T>) => {
    state = { ...state, ...update };
    listeners.forEach((fn) => fn());
  };
  operationManager.registerTransientCleanup(() => {
    state = initial();
    listeners.forEach((fn) => fn());
  });
  return {
    get: () => state,
    set,
    use: () =>
      useSyncExternalStore(
        (fn) => {
          listeners.add(fn);
          return () => {
            listeners.delete(fn);
          };
        },
        () => state,
      ),
  };
}
