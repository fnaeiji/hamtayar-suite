import { useEffect, useSyncExternalStore } from 'react';
import { metadataConfigService } from './metadataConfigService';
export function useMetadata() {
  const state = useSyncExternalStore(
    metadataConfigService.subscribe,
    metadataConfigService.getSnapshot,
  );
  useEffect(() => {
    if (!metadataConfigService.getSnapshot().loaded) metadataConfigService.load();
  }, []);
  return state;
}
