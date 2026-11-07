import { afterEach, expect, it } from 'vitest';
import { operationManager } from '../../src/services/operations/operationManager';
import { runOperation } from '../../src/services/operations/operationService';
import { createWorkspaceStore } from '../../src/services/operations/workspaceStore';
afterEach(() => operationManager.logout());
it('rejects duplicate submit, invalidates late results on logout, and resets drafts repeatedly', async () => {
  let finish!: (value: string) => void;
  let calls = 0;
  const work = () => {
    calls++;
    return new Promise<string>((resolve) => {
      finish = resolve;
    });
  };
  const pending = runOperation('test', 'demo', work);
  await runOperation('test', 'demo', work);
  expect(calls).toBe(1);
  operationManager.logout();
  finish('late');
  await pending;
  expect(operationManager.get('test')).toBeUndefined();
  const store = createWorkspaceStore(() => ({ text: '' }));
  store.set({ text: 'first' });
  operationManager.clearTransient();
  expect(store.get().text).toBe('');
  store.set({ text: 'second' });
  operationManager.logout();
  expect(store.get().text).toBe('');
});
it('keeps network-loss upload outcomes uncertain without fixture fallback', async () => {
  await runOperation(
    'upload',
    'api',
    async () => {
      throw { kind: 'network' };
    },
    true,
  );
  expect(operationManager.get('upload')).toMatchObject({
    status: 'uncertain',
    provenance: 'none',
  });
  expect(operationManager.get('upload')?.result).toBeUndefined();
});
