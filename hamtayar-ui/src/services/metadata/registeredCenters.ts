import { createWorkspaceStore } from '../operations/workspaceStore';

/** Centers of successfully completed demo documents; session memory, never backend evidence. */
const store = createWorkspaceStore(() => ({ centers: [] as string[] }));
export const registeredCenters = {
  use: store.use,
  get: () => store.get().centers,
  add(value: unknown) {
    if (typeof value !== 'string') return;
    const center = value.trim().replace(/\s+/g, ' ');
    if (!center || store.get().centers.includes(center)) return;
    store.set({ centers: [...store.get().centers, center] });
  },
};
