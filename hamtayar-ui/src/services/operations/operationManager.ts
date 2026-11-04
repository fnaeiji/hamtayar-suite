import type {
  OperationMode,
  OperationRecord,
  OperationStatus,
  OperationUpdate,
} from '../../types/operations';

type Listener = () => void;
type Cleanup = () => void;

class OperationManager {
  private records = new Map<string, OperationRecord>();
  private generations = new Map<string, number>();
  private listeners = new Set<Listener>();
  private cleanups = new Map<string, Set<Cleanup>>();
  private transientCleanups = new Set<Cleanup>();

  subscribe = (listener: Listener): Cleanup => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): readonly OperationRecord[] => [...this.records.values()];

  getPendingSnapshot = (): boolean => this.hasPending();

  get<TResult = unknown>(id: string): OperationRecord<TResult> | undefined {
    return this.records.get(id) as OperationRecord<TResult> | undefined;
  }

  hasPending(): boolean {
    return [...this.records.values()].some(({ status }) => status === 'pending');
  }

  begin(id: string, mode: OperationMode): OperationRecord {
    const previous = this.records.get(id);
    if (previous?.status === 'pending') return previous;
    this.cleanOperation(id);
    const generation = (this.generations.get(id) ?? 0) + 1;
    this.generations.set(id, generation);
    const now = Date.now();
    const record: OperationRecord = {
      id,
      generation,
      mode,
      status: 'validating',
      provenance: 'none',
      startedAt: now,
      updatedAt: now,
    };
    this.records.set(id, record);
    this.emit();
    return record;
  }

  update<TResult>(
    id: string,
    generation: number,
    update: OperationUpdate<TResult>,
  ): boolean {
    const current = this.records.get(id);
    if (!current || current.generation !== generation) return false;
    if (update.status && !this.canTransition(current.status, update.status)) return false;
    this.records.set(id, { ...current, ...update, updatedAt: Date.now() });
    this.emit();
    return true;
  }

  registerCleanup(id: string, cleanup: Cleanup): Cleanup {
    const cleanups = this.cleanups.get(id) ?? new Set<Cleanup>();
    cleanups.add(cleanup);
    this.cleanups.set(id, cleanups);
    return () => {
      cleanups.delete(cleanup);
      if (cleanups.size === 0) this.cleanups.delete(id);
    };
  }

  registerTransientCleanup(cleanup: Cleanup): Cleanup {
    this.transientCleanups.add(cleanup);
    return () => this.transientCleanups.delete(cleanup);
  }

  clearTransient(): void {
    for (const cleanup of this.transientCleanups) cleanup();
    for (const [id, record] of this.records) {
      if (record.status === 'pending') continue;
      this.cleanOperation(id);
      this.records.delete(id);
    }
    this.emit();
  }

  logout(): void {
    for (const [id, record] of this.records) {
      this.cleanOperation(id);
      this.generations.set(id, record.generation + 1);
    }
    this.records.clear();
    for (const cleanup of this.transientCleanups) cleanup();
    this.emit();
  }

  private canTransition(from: OperationStatus, to: OperationStatus): boolean {
    if (from === to) return true;
    const allowed: Record<OperationStatus, OperationStatus[]> = {
      idle: ['validating'],
      validating: ['pending', 'failed'],
      pending: ['completed', 'failed', 'uncertain'],
      completed: ['validating'],
      failed: ['validating'],
      uncertain: ['validating'],
    };
    return allowed[from].includes(to);
  }

  private cleanOperation(id: string): void {
    const cleanups = this.cleanups.get(id);
    if (cleanups) this.runCleanups(cleanups);
    this.cleanups.delete(id);
  }

  private runCleanups(cleanups: Set<Cleanup>): void {
    for (const cleanup of cleanups) {
      try {
        cleanup();
      } catch {
        // Cleanup must not prevent other observers from being released.
      }
    }
    cleanups.clear();
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }
}

export const operationManager = new OperationManager();
