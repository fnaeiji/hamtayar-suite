import {
  createContext,
  useContext,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { operationManager } from '../services/operations/operationManager';
import type { OperationMode } from '../types/operations';

type ModeContextValue = {
  mode: OperationMode;
  canSwitchMode: boolean;
  switchMode: (nextMode: OperationMode) => boolean;
};

const ModeContext = createContext<ModeContextValue | null>(null);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<OperationMode>('demo');
  const hasPending = useSyncExternalStore(
    operationManager.subscribe,
    operationManager.getPendingSnapshot,
    () => false,
  );
  const canSwitchMode = !hasPending;

  const value = useMemo<ModeContextValue>(
    () => ({
      mode,
      canSwitchMode,
      switchMode(nextMode) {
        if (nextMode === mode) return true;
        if (operationManager.hasPending()) return false;
        operationManager.clearTransient();
        setMode(nextMode);
        return true;
      },
    }),
    [canSwitchMode, mode],
  );

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode(): ModeContextValue {
  const value = useContext(ModeContext);
  if (!value) throw new Error('useMode must be used inside ModeProvider.');
  return value;
}
